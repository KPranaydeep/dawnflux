package app.dawnflux;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class LaunchTest {
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
                assertTrue(contains(root,"Save selected session as CSV"));
            });
            app.recreate();
            app.onActivity(activity->assertTrue(contains(activity.findViewById(android.R.id.content),"Saved sessions")));
        }
    }
}
