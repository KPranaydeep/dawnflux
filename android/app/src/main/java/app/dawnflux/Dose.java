package app.dawnflux;

/** Pure deterministic v1 trapezoidal integral; time unit is milliseconds. */
public final class Dose {
    public long lastTime = -1;
    public double lastLux, total;
    public boolean gapped;

    public boolean add(long time, double lux) {
        if (!Double.isFinite(lux) || lux < 0 || time < 0) throw new IllegalArgumentException("Invalid reading");
        if (lastTime >= 0 && time <= lastTime) return false;
        if (lastTime >= 0) {
            long gap = time - lastTime;
            if (gap > 120_000) gapped = true;
            else total += (lastLux + lux) / 2 * gap / 60_000.0;
        }
        lastTime = time;
        lastLux = lux;
        return true;
    }
}
