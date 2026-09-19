package app.dawnflux;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.os.SystemClock;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class LaunchTest {
    @Test public void runningSessionShowsNumericTimeAndStaleReason() {
        try(ActivityScenario<MainActivity> app=ActivityScenario.launch(MainActivity.class)) {
            app.onActivity(activity-> {
                try {
                    LightService.running=true;
                    LightService.total=5000; LightService.target=10000; LightService.lux=500;
                    LightService.etaReliable=true; LightService.lastArrival=SystemClock.elapsedRealtime();
                    activity.renderProgress();
                    View root=activity.findViewById(android.R.id.content);
                    assertTrue(contains(root,"Estimated time to target"));
                    assertTrue(contains(root,"about 10 min 0 sec"));
                    assertTrue(contains(root,"Save sleep"));
                    assertTrue(activity.findViewById(R.id.sleep_onset).isEnabled());
                    assertTrue(activity.findViewById(R.id.sleep_wake).isEnabled());
                    assertTrue(activity.findViewById(R.id.sleep_score).isEnabled());
                    LightService.lastArrival=0;
                    activity.renderProgress();
                    assertTrue(contains(root,"waiting for fresh readings"));
                } finally {
                    LightService.running=false; LightService.total=0; LightService.target=0;
                    LightService.lastArrival=0; LightService.etaReliable=false;
                }
            });
        }
    }
    private boolean contains(View view,String text) {
        if(view instanceof TextView && ((TextView)view).getText().toString().contains(text)) return true;
        if(view instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++) if(contains(group.getChildAt(i),text)) return true;
        }
        return false;
    }
    @Test public void opensAndSurvivesRecreation() {
        try(ActivityScenario<MainActivity> app=ActivityScenario.launch(MainActivity.class)) {
            app.onActivity(activity-> {
                View root=activity.findViewById(android.R.id.content);
                assertTrue(contains(root,"Morning light recharge"));
                assertTrue(contains(root,"Start light session"));
                assertTrue(contains(root,"Estimated time to target"));
                assertTrue(contains(root,"Start a light session to calculate"));
                assertTrue(contains(root,"Save selected session as CSV"));
            });
            app.recreate();
            app.onActivity(activity->assertTrue(contains(activity.findViewById(android.R.id.content),"Saved sessions")));
        }
    }
}
