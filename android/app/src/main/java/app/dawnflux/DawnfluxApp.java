package app.dawnflux;

import android.app.Application;

public class DawnfluxApp extends Application {
    @Override public void onCreate() {
        super.onCreate();
        // A fresh process never pretends to have recorded while it was dead.
        try (Store store = new Store(this)) { store.interruptActive(); }
    }
}
