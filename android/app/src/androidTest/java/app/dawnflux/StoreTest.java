package app.dawnflux;
import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.time.ZonedDateTime;
import java.time.OffsetDateTime;
import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class StoreTest {
    @Test public void upgradesWithoutLosingSessionsAndPersistsSleep() throws Exception {
        Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        context.deleteDatabase("dawnflux.db");
        try {
            try(SQLiteDatabase old=context.openOrCreateDatabase("dawnflux.db",0,null)) {
                old.execSQL("CREATE TABLE sessions(id TEXT PRIMARY KEY,wake TEXT NOT NULL,target REAL NOT NULL,quality TEXT NOT NULL,state TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL)");
                old.execSQL("CREATE TABLE samples(session TEXT NOT NULL,time INTEGER NOT NULL,lux REAL NOT NULL,dose REAL NOT NULL,PRIMARY KEY(session,time))");
                old.execSQL("INSERT INTO sessions VALUES ('test-session','2026-09-19T06:00+05:30',10000,'good','complete','Test',1)");
                old.setVersion(1);
            }
            try(Store store=new Store(context)) {
                assertEquals(1,store.sessions().size());
                store.sample("test-session",OffsetDateTime.parse("2026-09-19T07:30+05:30").toInstant().toEpochMilli(),500,0,"good");
                store.saveSleep(SleepEntry.create("23:00","07:00","90",ZonedDateTime.parse("2026-09-19T09:00+05:30")));
                assertEquals("2026-09-19T07:00+05:30",store.sessions().get(0).wake);
                try {
                    store.saveSleep(SleepEntry.create("23:00","08:00","20",ZonedDateTime.parse("2026-09-19T09:00+05:30")));
                    fail("Wake after readings must be rejected");
                } catch(IllegalArgumentException expected) { }
            }
            try(Store reopened=new Store(context)) {
                assertEquals(1,reopened.sleepRows().length());
                assertEquals(90,reopened.sleepRows().getJSONObject(0).getDouble("sleep_score"),0.001);
                assertEquals(1,reopened.samples("test-session").size());
            }
        } finally { context.deleteDatabase("dawnflux.db"); }
    }
}
