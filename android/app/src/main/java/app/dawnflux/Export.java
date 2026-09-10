package app.dawnflux;

import org.json.JSONArray;
import org.json.JSONObject;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

public final class Export {
    public static final String[] COLUMNS = {"session_id","date","timestamp","lux","cumulative_lux_minutes","wake_time","session_start","session_end","minutes_after_waking","target_lux_minutes","target_reached","measurement_quality"};
    private static String timestamp(long time, ZoneOffset offset) { return Instant.ofEpochMilli(time).atOffset(offset).toString(); }
    public static JSONArray rows(Store.Session s, List<Store.Sample> samples) throws Exception {
        if (s.state.equals("active")) throw new IllegalArgumentException("Stop the session before exporting.");
        if (samples.size() < 2) throw new IllegalArgumentException("At least two real readings are needed. This session is kept locally but cannot be imported into Dawnflux.");
        ZoneOffset offset = OffsetDateTime.parse(s.wake).getOffset();
        long first = samples.get(0).time, last = samples.get(samples.size()-1).time;
        String start = timestamp(first, offset), end = timestamp(last, offset);
        double delay = (first - OffsetDateTime.parse(s.wake).toInstant().toEpochMilli()) / 60000.0;
        JSONArray rows = new JSONArray();
        for (Store.Sample sample : samples) {
            JSONObject row = new JSONObject();
            Object[] values = {s.id,start.substring(0,10),timestamp(sample.time,offset),sample.lux,sample.dose,s.wake,start,end,delay,s.target,sample.dose>=s.target,s.quality};
            for(int i=0;i<COLUMNS.length;i++) row.put(COLUMNS[i],values[i]);
            rows.put(row);
        }
        return rows;
    }
    public static String csv(Store.Session s, List<Store.Sample> samples) throws Exception {
        JSONArray rows = rows(s,samples);
        StringBuilder out = new StringBuilder(String.join(",", COLUMNS)).append('\n');
        for (int r=0;r<rows.length();r++) {
            JSONObject row = rows.getJSONObject(r);
            for(int c=0;c<COLUMNS.length;c++) {
                if(c>0) out.append(',');
                out.append('"').append(row.get(COLUMNS[c]).toString().replace("\"", "\"\"")).append('"');
            }
            out.append('\n');
        }
        return out.toString();
    }
    public static String json(Store.Session s, List<Store.Sample> samples) throws Exception {
        return new JSONObject().put("schema_version",1).put("morning_light",rows(s,samples)).toString(2);
    }
}
