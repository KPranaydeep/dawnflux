package app.dawnflux;

/** Remaining dose / latest measured lux. An estimate, never invented exposure. */
public final class Eta {
    private Eta() { }

    public static String label(double total, double target, double lux, boolean fresh, boolean reliable) {
        if (!Double.isFinite(total) || !Double.isFinite(target) || total < 0 || target <= 0)
            return "ETA unavailable";
        if (total >= target) return "ETA: 0 sec · target reached";
        if (!fresh) return "ETA: waiting for fresh readings";
        if (!reliable || !Double.isFinite(lux) || lux < 0) return "ETA unavailable · check sensor";
        if (lux == 0) return "ETA: waiting for light";
        double seconds = Math.ceil((target - total) / lux * 60.0);
        if (!Double.isFinite(seconds) || seconds > 86400) return "ETA: more than 24 hours at current light";
        long remaining = Math.max(1, (long) seconds);
        long hours = remaining / 3600, minutes = (remaining % 3600) / 60, secs = remaining % 60;
        String duration = hours > 0 ? hours + " hr " + minutes + " min"
            : minutes > 0 ? minutes + " min " + secs + " sec" : secs + " sec";
        return "ETA: about " + duration + " at current light";
    }
}
