package app.dawnflux;
import org.junit.Test;
import org.json.JSONObject;
import java.time.ZonedDateTime;
import static org.junit.Assert.*;
public class SleepEntryTest {
    private final ZonedDateTime now=ZonedDateTime.parse("2026-09-19T10:00:00+05:30");
    @Test public void derivesOvernightDatesAndDurationWithoutInventingBedtime() throws Exception {
        JSONObject r=SleepEntry.create("23:30","07:00","80",now);
        assertEquals("2026-09-19",r.getString("date"));
        assertEquals("2026-09-18T23:30+05:30",r.getString("sleep_onset"));
        assertEquals(7.5,r.getDouble("sleep_duration"),0.001);
        assertTrue(r.isNull("bedtime")); assertTrue(r.isNull("sleep_regularity"));
    }
    @Test public void handlesSleepAfterMidnight() throws Exception {
        JSONObject r=SleepEntry.create("01:00","07:00","0",now);
        assertEquals("2026-09-19T01:00+05:30",r.getString("sleep_onset"));
        assertEquals(6,r.getDouble("sleep_duration"),0.001);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsFutureWake() throws Exception { SleepEntry.create("23:00","11:00","80",now); }
    @Test(expected=IllegalArgumentException.class) public void rejectsEqualTimes() throws Exception { SleepEntry.create("07:00","07:00","80",now); }
    @Test(expected=IllegalArgumentException.class) public void rejectsInvalidScore() throws Exception { SleepEntry.create("23:00","07:00","NaN",now); }
    @Test(expected=IllegalArgumentException.class) public void rejectsAmbiguousClockChange() throws Exception {
        SleepEntry.create("01:30","07:00","80",ZonedDateTime.parse("2026-11-01T08:00:00-05:00[America/New_York]"));
    }
}
