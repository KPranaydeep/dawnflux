package app.dawnflux;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.util.ArrayList;
import java.util.List;

/** App-private, durable raw data; Android backup is disabled in the manifest. */
public class Store extends SQLiteOpenHelper {
    public Store(Context context) { super(context, "dawnflux.db", null, 2); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE sessions(id TEXT PRIMARY KEY,wake TEXT NOT NULL,target REAL NOT NULL,quality TEXT NOT NULL,state TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE samples(session TEXT NOT NULL,time INTEGER NOT NULL,lux REAL NOT NULL,dose REAL NOT NULL,PRIMARY KEY(session,time))");
        createSleep(db);
    }
    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) { if(oldVersion<2) createSleep(db); }
    private void createSleep(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS sleep(date TEXT PRIMARY KEY,payload TEXT NOT NULL)");
    }
    public void saveSleep(org.json.JSONObject row) throws Exception {
        String day=row.getString("date"), wake=row.getString("wake_time");
        long wakeMillis=java.time.OffsetDateTime.parse(wake).toInstant().toEpochMilli();
        SQLiteDatabase db=getWritableDatabase(); db.beginTransaction();
        try {
            try(Cursor c=db.rawQuery("SELECT MIN(time) FROM samples JOIN sessions ON samples.session=sessions.id WHERE substr(wake,1,10)=?",new String[]{day})) {
                if(c.moveToFirst()&&!c.isNull(0)&&c.getLong(0)<wakeMillis)
                    throw new IllegalArgumentException("Wake time must be before today's light readings.");
            }
            ContentValues v=new ContentValues(); v.put("date",day); v.put("payload",row.toString());
            db.insertWithOnConflict("sleep",null,v,SQLiteDatabase.CONFLICT_REPLACE);
            ContentValues w=new ContentValues(); w.put("wake",wake);
            db.update("sessions",w,"substr(wake,1,10)=?",new String[]{day});
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    public org.json.JSONArray sleepRows() throws Exception {
        org.json.JSONArray rows=new org.json.JSONArray();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT payload FROM sleep ORDER BY date",null)) {
            while(c.moveToNext()) rows.put(new org.json.JSONObject(c.getString(0)));
        }
        return rows;
    }
    public void interruptActive() {
        getWritableDatabase().execSQL("UPDATE sessions SET state='interrupted',quality='poor',reason='Recording process stopped; no readings inferred.' WHERE state='active'");
    }
    public void create(String id, String wake, double target) {
        ContentValues v = new ContentValues();
        v.put("id", id); v.put("wake", wake); v.put("target", target); v.put("quality", "good");
        v.put("state", "active"); v.put("reason", "Recording"); v.put("created", System.currentTimeMillis());
        getWritableDatabase().insertOrThrow("sessions", null, v);
    }
    public void sample(String id, long time, double lux, double dose, String quality) {
        SQLiteDatabase db = getWritableDatabase(); db.beginTransaction();
        try {
            ContentValues v = new ContentValues(); v.put("session", id); v.put("time", time); v.put("lux", lux); v.put("dose", dose);
            db.insertOrThrow("samples", null, v);
            ContentValues q = new ContentValues(); q.put("quality", quality);
            db.update("sessions", q, "id=?", new String[]{id}); db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    public void finish(String id, String state, String quality, String reason) {
        ContentValues v = new ContentValues(); v.put("state", state); v.put("quality", quality); v.put("reason", reason);
        getWritableDatabase().update("sessions", v, "id=?", new String[]{id});
    }
    public List<Session> sessions() {
        List<Session> result = new ArrayList<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT id,wake,target,quality,state,reason FROM sessions ORDER BY created DESC", null)) {
            while (c.moveToNext()) result.add(new Session(c.getString(0), c.getString(1), c.getDouble(2), c.getString(3), c.getString(4), c.getString(5)));
        }
        return result;
    }
    public List<Sample> samples(String id) {
        List<Sample> result = new ArrayList<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT time,lux,dose FROM samples WHERE session=? ORDER BY time", new String[]{id})) {
            while (c.moveToNext()) result.add(new Sample(c.getLong(0), c.getDouble(1), c.getDouble(2)));
        }
        return result;
    }
    public static final class Session {
        public final String id, wake, quality, state, reason;
        public final double target;
        Session(String id, String wake, double target, String quality, String state, String reason) {
            this.id=id; this.wake=wake; this.target=target; this.quality=quality; this.state=state; this.reason=reason;
        }
        @Override public String toString() { return wake.substring(0,10) + " · " + state + " · " + id.substring(0,8); }
    }
    public static final class Sample {
        public final long time;
        public final double lux, dose;
        Sample(long time, double lux, double dose) { this.time=time; this.lux=lux; this.dose=dose; }
    }
}
