package app.dawnflux;

import org.junit.Test;
import org.json.JSONObject;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.List;
import static org.junit.Assert.*;

public class ExportTest {
    private Store.Session session(String state,String quality) {
        return new Store.Session("00000000-0000-0000-0000-000000000001","2026-09-10T07:00:00+05:30",1000,quality,state,"Synthetic fixture");
    }
    @Test public void exportsActualJavaRowsForPythonContractTests() throws Exception {
        long start=OffsetDateTime.parse("2026-09-10T07:20:00+05:30").toInstant().toEpochMilli();
        List<Store.Sample> samples=List.of(new Store.Sample(start,500,0),new Store.Sample(start+60_000,1500,1000),new Store.Sample(start+240_000,800,1000));
        Store.Session s=session("complete","gapped");
        String json=Export.json(s,samples),csv=Export.csv(s,samples);
        JSONObject object=new JSONObject(json);
        assertEquals(12,object.getJSONArray("morning_light").getJSONObject(0).length());
        assertTrue(object.getJSONArray("morning_light").getJSONObject(1).getBoolean("target_reached"));
        assertFalse(object.has("settings"));
        Path dir=Path.of("build","contract-fixtures"); Files.createDirectories(dir);
        Files.write(dir.resolve("android-session.json"),json.getBytes(StandardCharsets.UTF_8));
        Files.write(dir.resolve("android-session.csv"),csv.getBytes(StandardCharsets.UTF_8));
    }
    @Test(expected=IllegalArgumentException.class) public void activeSessionCannotExport() throws Exception { Export.rows(session("active","good"),List.of()); }
    @Test(expected=IllegalArgumentException.class) public void emptySessionCannotExport() throws Exception { Export.rows(session("complete","poor"),List.of()); }
}
