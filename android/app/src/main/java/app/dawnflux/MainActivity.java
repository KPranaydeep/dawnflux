package app.dawnflux;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.hardware.*;
import android.os.*;
import android.provider.Settings;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;

public class MainActivity extends Activity {
    private final Handler handler=new Handler(Looper.getMainLooper());
    private Store store;
    private TextView live, detail, estimatedTime;
    private EditText wakeInput,targetInput,onsetInput,scoreInput;
    private TextView sleepStatus;
    private Button start,stop;
    private Spinner history;
    private Gauge gauge;
    private List<Store.Session> sessions=new ArrayList<>();
    private String exportId,exportFormat;
    private boolean previousRunning;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state); store=new Store(this); LightService.channels(this);
        if(state!=null) { exportId=state.getString("exportId"); exportFormat=state.getString("exportFormat"); }
        ScrollView scroll=new ScrollView(this);
        LinearLayout body=new LinearLayout(this); body.setOrientation(LinearLayout.VERTICAL); body.setPadding(dp(24),dp(20),dp(24),dp(24));
        scroll.addView(body); setContentView(scroll);
        scroll.setOnApplyWindowInsetsListener((v,insets)-> {
            if(Build.VERSION.SDK_INT>=30) {
                Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
                v.setPadding(bars.left,bars.top,bars.right,bars.bottom);
            } else v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        text(body,"Dawnflux",30);
        text(body,"Morning light recharge",19);
        text(body,"Keep the phone's light sensor uncovered. This measures light at your phone, not a body battery. You can lock the screen after starting.",15);
        Sensor sensor=LightService.findSensor(getSystemService(SensorManager.class));
        text(body,sensor==null?"No ambient-light sensor found. Recording is unavailable.":"Sensor: "+sensor.getName()+"\nWake-up sensor: "+sensor.isWakeUpSensor()+" · maximum "+sensor.getMaximumRange()+" lux",13);
        gauge=new Gauge(this); body.addView(gauge,new LinearLayout.LayoutParams(-1,dp(80)));
        text(body,"Estimated time to target",19);
        estimatedTime=text(body,"Start a light session to calculate",24);
        text(body,"Dawnflux 0.3.0",12);
        live=text(body,"Ready",19);
        text(body,"Sleep ending today · "+LocalDate.now(),22);
        text(body,"Fell asleep (HH:mm)",15);
        onsetInput=new EditText(this); onsetInput.setId(R.id.sleep_onset); onsetInput.setSingleLine(true); onsetInput.setHint("23:00"); body.addView(onsetInput);
        text(body,"Woke up (HH:mm)",15);
        wakeInput=new EditText(this); wakeInput.setId(R.id.sleep_wake); wakeInput.setSingleLine(true); wakeInput.setHint("07:00");
        wakeInput.setText(getPreferences(0).getString("wake","07:00")); body.addView(wakeInput);
        text(body,"Sleep score (0-100)",15);
        scoreInput=new EditText(this); scoreInput.setId(R.id.sleep_score); scoreInput.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL); body.addView(scoreInput);
        button(body,"Save sleep",v->saveSleep());
        sleepStatus=text(body,"Enter last night's sleep here, even while light recording is running. Wake date is today; an evening sleep time means the previous night.",14);
        loadSleep();
        text(body,"Target (lux·minutes)",15);
        targetInput=new EditText(this); targetInput.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);
        targetInput.setText(getPreferences(0).getString("target","10000")); body.addView(targetInput);
        text(body,"Use your Dawnflux target here. 10,000 is only a placeholder. ETA assumes the current light stays constant; it can change as you move. Sessions stop automatically after two hours even if the ETA is longer.",13);
        start=button(body,"Start light session",v->startSession());
        stop=button(body,"Stop and save",v->startService(new Intent(this,LightService.class).setAction(LightService.STOP)));
        button(body,"Notification settings",v->startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName())));
        button(body,"Battery / background settings",v->startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName()))));
        text(body,"On OxygenOS, allow background activity for Dawnflux if recording stops when locked. Run a short locked-screen test first; missing readings are never guessed.",13);
        button(body,"Export dashboard upload (light + sleep)",v->exportBundle());
        text(body,"One JSON file includes all finished light sessions with at least two readings and all saved sleep entries. Stop recording first to include the current session. Upload using JSON in the dashboard; no retyping needed.",14);
        text(body,"Saved sessions",22);
        history=new Spinner(this); body.addView(history);
        detail=text(body,"No sessions yet",15);
        history.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> parent,View view,int position,long id) { showSession(); }
            @Override public void onNothingSelected(android.widget.AdapterView<?> parent) { }
        });
        button(body,"Save selected session as CSV",v->export("csv"));
        button(body,"Save selected session as JSON",v->export("json"));
        text(body,"After stopping: save CSV or JSON to Downloads, then upload it in Dawnflux → Import / export. Your readings stay on this phone unless you export them. No website or internet is needed while recording.",15);
        reloadHistory(); previousRunning=LightService.running;
    }
    private void loadSleep() {
        try {
            org.json.JSONArray rows=store.sleepRows();
            for(int i=0;i<rows.length();i++) {
                org.json.JSONObject row=rows.getJSONObject(i);
                if(row.getString("date").equals(LocalDate.now().toString())) {
                    onsetInput.setText(OffsetDateTime.parse(row.getString("sleep_onset")).toLocalTime().toString());
                    wakeInput.setText(OffsetDateTime.parse(row.getString("wake_time")).toLocalTime().toString());
                    scoreInput.setText(row.get("sleep_score").toString());
                    sleepStatus.setText(String.format(Locale.US,"Saved for %s · %.2f hours",row.getString("date"),row.getDouble("sleep_duration")));
                }
            }
        } catch(Exception ex) { message("Could not load sleep: "+ex.getMessage()); }
    }
    private void saveSleep() {
        try {
            org.json.JSONObject row=SleepEntry.create(onsetInput.getText().toString(),wakeInput.getText().toString(),scoreInput.getText().toString(),ZonedDateTime.now());
            store.saveSleep(row);
            getPreferences(0).edit().putString("wake",wakeInput.getText().toString().trim()).apply();
            loadSleep(); reloadHistory();
        } catch(Exception ex) { message("Sleep not saved: "+ex.getMessage()); }
    }
    private String bundle() throws Exception {
        org.json.JSONArray light=new org.json.JSONArray();
        for(Store.Session s:store.sessions()) {
            List<Store.Sample> samples=store.samples(s.id);
            if(s.state.equals("active")||samples.size()<2) continue;
            org.json.JSONArray rows=Export.rows(s,samples);
            for(int i=0;i<rows.length();i++) light.put(rows.get(i));
        }
        org.json.JSONArray sleep=store.sleepRows();
        if(light.length()==0&&sleep.length()==0) throw new IllegalArgumentException("Save sleep or finish a light session first.");
        return Export.combined(light,sleep);
    }
    private void exportBundle() {
        try {
            bundle(); exportFormat="bundle"; exportId=null;
            startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType("application/json").putExtra(Intent.EXTRA_TITLE,"dawnflux-dashboard-"+LocalDate.now()+".json"),20);
        } catch(Exception ex) { message(ex.getMessage()); }
    }
    private int dp(int n) { return Math.round(n*getResources().getDisplayMetrics().density); }
    private TextView text(LinearLayout body,String value,int size) {
        TextView t=new TextView(this); t.setText(value); t.setTextSize(size); t.setPadding(0,dp(8),0,dp(8)); body.addView(t); return t;
    }
    private Button button(LinearLayout body,String label,View.OnClickListener action) {
        Button b=new Button(this); b.setText(label); b.setAllCaps(false); b.setOnClickListener(action); body.addView(b); return b;
    }
    private void startSession() {
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},10); return;
        }
        if(!LightService.notificationsReady(this)) { message("Enable notifications for both progress and target alerts, then tap Start again."); return; }
        try {
            if(LightService.running) return;
            double target=Double.parseDouble(targetInput.getText().toString());
            LocalTime clock=LocalTime.parse(wakeInput.getText().toString().trim());
            ZonedDateTime now=ZonedDateTime.now();
            java.time.LocalDateTime local=now.toLocalDate().atTime(clock);
            if(now.getZone().getRules().getValidOffsets(local).size()!=1) throw new IllegalArgumentException("Wake time is ambiguous or nonexistent in this timezone.");
            ZonedDateTime wake=local.atZone(now.getZone());
            if(wake.isAfter(now)||!Double.isFinite(target)||target<1||target>10000000) throw new IllegalArgumentException("Use a wake time before now and target between 1 and 10,000,000.");
            getPreferences(0).edit().putString("wake",clock.toString()).putString("target",Double.toString(target)).apply();
            startForegroundService(new Intent(this,LightService.class).putExtra("wake",wake.toOffsetDateTime().toString()).putExtra("target",target));
        } catch(Exception ex) { message(ex.getMessage()==null?"Check wake time and target":ex.getMessage()); }
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results) {
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==10) message(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED?"Notifications allowed. Tap Start light session when ready.":"Recording needs notifications so the active session and target alert remain visible.");
    }
    private final Runnable refresh=new Runnable() {
        @Override public void run() {
            renderProgress();
            handler.postDelayed(this,1000);
        }
    };
    void renderProgress() {
            boolean active=LightService.running;
            start.setEnabled(!active); stop.setEnabled(active); wakeInput.setEnabled(true); targetInput.setEnabled(!active);
            if(active) {
                double percent=100*LightService.total/Math.max(1,LightService.target);
                long age=LightService.lastArrival==0?0:(SystemClock.elapsedRealtime()-LightService.lastArrival)/1000;
                estimatedTime.setText(LightService.eta());
                live.setText(String.format(Locale.US,"%.0f lux · %.1f / %.0f lux·min\n%s\nLast reading: %s",LightService.lux,LightService.total,LightService.target,LightService.status,LightService.lastArrival==0?"waiting":age+" seconds ago"));
                gauge.percent=(float)Math.min(100,percent); gauge.invalidate();
            } else {
                estimatedTime.setText("Start a light session to calculate");
                live.setText(LightService.status);
            }
            if(active!=previousRunning) { previousRunning=active; reloadHistory(); }
    }
    private void reloadHistory() {
        sessions=store.sessions(); history.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,sessions)); showSession();
    }
    private Store.Session selected() {
        int i=history.getSelectedItemPosition(); return i>=0&&i<sessions.size()?sessions.get(i):null;
    }
    private void showSession() {
        Store.Session s=selected(); if(s==null) { detail.setText("No sessions yet"); return; }
        List<Store.Sample> samples=store.samples(s.id);
        detail.setText(String.format(Locale.US,"%s\n%s · %s\n%d readings · %.1f lux·min\n%s",s.id,s.state,s.quality,samples.size(),samples.isEmpty()?0:samples.get(samples.size()-1).dose,s.reason));
    }
    private void export(String format) {
        Store.Session s=selected(); if(s==null) { message("Record a session first."); return; }
        try {
            Export.rows(s,store.samples(s.id)); // Validate before opening the picker.
            exportId=s.id; exportFormat=format;
            startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType(format.equals("csv")?"text/csv":"application/json")
                .putExtra(Intent.EXTRA_TITLE,"dawnflux-"+s.id+"."+format),20);
        } catch(Exception ex) { message(ex.getMessage()); }
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request!=20||result!=RESULT_OK||data==null||data.getData()==null) return;
        try {
            Store.Session session=null;
            for(Store.Session s:store.sessions()) if(s.id.equals(exportId)) session=s;
            if(session==null&&!"bundle".equals(exportFormat)) throw new IllegalStateException("Session no longer available");
            String content="bundle".equals(exportFormat)?bundle():"csv".equals(exportFormat)?Export.csv(session,store.samples(session.id)):Export.json(session,store.samples(session.id));
            try(OutputStream out=getContentResolver().openOutputStream(data.getData(),"wt")) {
                if(out==null) throw new IllegalStateException("Could not open the export file");
                out.write(content.getBytes(StandardCharsets.UTF_8));
            }
            message("Saved. Upload this file in Dawnflux → Import / export.");
        } catch(Exception ex) { message("Export failed: "+ex.getMessage()); }
    }
    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); out.putString("exportId",exportId); out.putString("exportFormat",exportFormat); }
    @Override protected void onResume() { super.onResume(); reloadHistory(); handler.post(refresh); }
    @Override protected void onPause() { handler.removeCallbacks(refresh); super.onPause(); }
    @Override protected void onDestroy() { handler.removeCallbacksAndMessages(null); store.close(); super.onDestroy(); }
    private void message(String text) { new AlertDialog.Builder(this).setMessage(text).setPositiveButton("OK",null).show(); }
    private static final class Gauge extends View {
        float percent;
        final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Gauge(Context context) { super(context); setContentDescription("Light target progress"); }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float w=getWidth(),h=getHeight();
            paint.setColor(Color.rgb(230,235,235)); canvas.drawRoundRect(0,12,w,h-12,18,18,paint);
            paint.setColor(Color.rgb(239,181,49)); canvas.drawRoundRect(0,12,w*percent/100,h-12,18,18,paint);
            paint.setColor(Color.rgb(25,40,43)); paint.setTextSize(24*getResources().getDisplayMetrics().scaledDensity); paint.setTextAlign(Paint.Align.CENTER);
            canvas.drawText(String.format(Locale.US,"%.0f%%",percent),w/2,h/2-(paint.ascent()+paint.descent())/2,paint);
        }
    }
}
