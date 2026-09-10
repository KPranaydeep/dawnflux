package app.dawnflux;

import android.Manifest;
import android.app.*;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.hardware.*;
import android.os.*;
import java.time.*;
import java.util.Locale;
import java.util.UUID;

/** Only user-started, bounded foreground sessions; never restarts silently. */
public class LightService extends Service implements SensorEventListener {
    public static final String STOP="app.dawnflux.STOP", ACTIVE="recording", ALERT="target";
    public static boolean running;
    public static String status="Ready", sessionId;
    public static double lux, total, target;
    public static long lastArrival, started;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Dose dose=new Dose();
    private SensorManager sensors;
    private Sensor sensor;
    private PowerManager.WakeLock lock;
    private Store store;
    private long anchorWall, anchorElapsed, refreshAt;
    private String quality="good";
    private boolean notified;
    private static final long MAX_DURATION=2*60*60*1000;

    public static Sensor findSensor(SensorManager manager) {
        Sensor wakeup=manager.getDefaultSensor(Sensor.TYPE_LIGHT,true);
        return wakeup!=null?wakeup:manager.getDefaultSensor(Sensor.TYPE_LIGHT);
    }
    public static void channels(android.content.Context context) {
        NotificationManager nm=context.getSystemService(NotificationManager.class);
        NotificationChannel active=new NotificationChannel(ACTIVE,"Light session progress",NotificationManager.IMPORTANCE_LOW);
        active.setDescription("Ongoing user-started morning-light recording");
        NotificationChannel alert=new NotificationChannel(ALERT,"Target and recording alerts",NotificationManager.IMPORTANCE_HIGH);
        alert.enableVibration(true);
        nm.createNotificationChannel(active); nm.createNotificationChannel(alert);
    }
    public static boolean notificationsReady(android.content.Context context) {
        NotificationManager nm=context.getSystemService(NotificationManager.class);
        return (Build.VERSION.SDK_INT<33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED)
            && nm.areNotificationsEnabled()
            && nm.getNotificationChannel(ACTIVE).getImportance()!=NotificationManager.IMPORTANCE_NONE
            && nm.getNotificationChannel(ALERT).getImportance()!=NotificationManager.IMPORTANCE_NONE;
    }
    @Override public void onCreate() {
        super.onCreate(); channels(this); store=new Store(this);
        sensors=getSystemService(SensorManager.class); sensor=findSensor(sensors);
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent==null) { stopSelf(); return START_NOT_STICKY; }
        if(STOP.equals(intent.getAction())) { finish("complete","Stopped by you"); return START_NOT_STICKY; }
        if(running) return START_NOT_STICKY;
        try {
            if(sensor==null) throw new IllegalArgumentException("No TYPE_LIGHT sensor available.");
            if(!notificationsReady(this)) throw new IllegalArgumentException("Enable both Dawnflux notification channels before starting.");
            double requested=intent.getDoubleExtra("target",0);
            OffsetDateTime wake=OffsetDateTime.parse(intent.getStringExtra("wake"));
            OffsetDateTime now=OffsetDateTime.now(wake.getOffset());
            if(!Double.isFinite(requested)||requested<1||requested>10000000||wake.isAfter(now)||!wake.toLocalDate().equals(now.toLocalDate()))
                throw new IllegalArgumentException("Choose a positive target and today's actual wake time before now.");
            target=requested; total=0; lux=0; lastArrival=0; status="Waiting for first sensor reading";
            Notification notification=notification(status);
            if(Build.VERSION.SDK_INT>=34) startForeground(1,notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            else startForeground(1,notification);
            anchorWall=System.currentTimeMillis(); anchorElapsed=SystemClock.elapsedRealtimeNanos(); started=SystemClock.elapsedRealtime();
            sessionId=UUID.randomUUID().toString(); store.create(sessionId,wake.toString(),target); running=true;
            lock=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"Dawnflux:LightSession");
            lock.acquire(MAX_DURATION+60_000);
            if(!sensors.registerListener(this,sensor,SensorManager.SENSOR_DELAY_NORMAL,handler)) throw new IllegalStateException("Sensor registration failed");
            refreshAt=started; handler.postDelayed(tick,1000);
        } catch(Exception ex) { quality="poor"; finish("interrupted",ex.getMessage()==null?"Could not start recording":ex.getMessage()); }
        return START_NOT_STICKY;
    }
    private final Runnable tick=new Runnable() {
        @Override public void run() {
            if(!running) return;
            long now=SystemClock.elapsedRealtime();
            if(now-started>=MAX_DURATION) { finish("complete","Two-hour session limit reached"); return; }
            if(!notificationsReady(LightService.this)) { quality="poor"; finish("interrupted","Notifications disabled during recording"); return; }
            if(now-(lastArrival==0?started:lastArrival)>120_000) {
                quality="poor"; finish("interrupted","Sensor stopped delivering readings for two minutes. No exposure invented."); return;
            }
            // TYPE_LIGHT may report only on change. Re-activation requests a fresh
            // hardware event; we NEVER integrate a timer-based copy of cached lux.
            if(now-refreshAt>=10_000) {
                sensors.unregisterListener(LightService.this);
                if(!sensors.registerListener(LightService.this,sensor,SensorManager.SENSOR_DELAY_NORMAL,handler)) {
                    quality="poor"; finish("interrupted","Sensor stopped accepting registration"); return;
                }
                refreshAt=now;
            }
            status=lastArrival==0?"Waiting for sensor":now-lastArrival>20_000?"Waiting for fresh readings — dose paused":"Recording · "+quality;
            getSystemService(NotificationManager.class).notify(1,notification(status));
            handler.postDelayed(this,1000);
        }
    };
    @Override public void onSensorChanged(SensorEvent event) {
        if(!running||event.values.length==0) return;
        long nowNanos=SystemClock.elapsedRealtimeNanos();
        // Reject stale/batched events and events predating this explicit session.
        if(event.timestamp<anchorElapsed||event.timestamp>nowNanos+1_000_000_000L||nowNanos-event.timestamp>5_000_000_000L) return;
        long time=anchorWall+(event.timestamp-anchorElapsed)/1_000_000;
        if(dose.lastTime>=0&&time-dose.lastTime<1000) return;
        double value=event.values[0];
        if(!Double.isFinite(value)||value<0) { quality="poor"; return; }
        if(value>=sensor.getMaximumRange()||event.accuracy==SensorManager.SENSOR_STATUS_UNRELIABLE) quality="poor";
        if(!dose.add(time,value)) return;
        if(dose.gapped&&!quality.equals("poor")) quality="gapped";
        try { store.sample(sessionId,time,value,dose.total,quality); }
        catch(Exception ex) { quality="poor"; finish("interrupted","Could not save sensor readings"); return; }
        lux=value; total=dose.total; lastArrival=SystemClock.elapsedRealtime();
        if(total>=target&&!notified) { notified=true; alert("Light target reached","Your measured exposure reached the session target. Tap Stop when you are done."); }
    }
    @Override public void onAccuracyChanged(Sensor sensor,int accuracy) {
        if(running&&accuracy==SensorManager.SENSOR_STATUS_UNRELIABLE) quality="poor";
    }
    private PendingIntent open() {
        return PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }
    private Notification notification(String text) {
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,LightService.class).setAction(STOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,ACTIVE).setSmallIcon(R.drawable.ic_sun).setContentTitle("Dawnflux · light recharge")
            .setContentText(String.format(Locale.US,"%.0f / %.0f lux·min · %.0f lux · %s",total,target,lux,text))
            .setStyle(new Notification.BigTextStyle().bigText(String.format(Locale.US,"%.0f / %.0f lux·min · %.0f lux\n%s",total,target,lux,text)))
            .setProgress(100,(int)Math.min(100,100*total/Math.max(1,target)),false)
            .setContentIntent(open()).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,"Stop",stop).build()).build();
    }
    private void alert(String title,String message) {
        getSystemService(NotificationManager.class).notify(2,new Notification.Builder(this,ALERT).setSmallIcon(R.drawable.ic_sun)
            .setContentTitle(title).setContentText(message).setStyle(new Notification.BigTextStyle().bigText(message))
            .setContentIntent(open()).setAutoCancel(true).build());
    }
    private void finish(String state,String reason) {
        boolean wasRunning=running;
        running=false; status=reason; handler.removeCallbacksAndMessages(null);
        if(sensors!=null) sensors.unregisterListener(this);
        if(lock!=null&&lock.isHeld()) lock.release();
        if(wasRunning&&sessionId!=null) {
            try { store.finish(sessionId,state,quality,reason); } catch(Exception ignored) { /* active record recovered as poor next process */ }
            alert(state.equals("complete")?"Session saved":"Session interrupted",reason);
        }
        stopForeground(STOP_FOREGROUND_REMOVE); stopSelf();
    }
    @Override public void onDestroy() {
        if(running) { quality="poor"; finish("interrupted","Service stopped unexpectedly"); }
        if(store!=null) store.close(); super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
