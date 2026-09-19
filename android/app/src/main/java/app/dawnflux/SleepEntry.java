package app.dawnflux;

import java.time.*;
import org.json.JSONObject;

/** Wake date is today; onset is the most recent occurrence before wake. */
public final class SleepEntry {
    public static JSONObject create(String fellAsleep,String wokeUp,String score,ZonedDateTime now) throws Exception {
        LocalTime onsetClock=LocalTime.parse(fellAsleep.trim());
        LocalTime wakeClock=LocalTime.parse(wokeUp.trim());
        LocalDate day=now.toLocalDate();
        LocalDateTime wakeLocal=day.atTime(wakeClock);
        LocalDateTime onsetLocal=day.atTime(onsetClock);
        if(!onsetClock.isBefore(wakeClock)) onsetLocal=onsetLocal.minusDays(1);
        ZoneId zone=now.getZone();
        if(zone.getRules().getValidOffsets(wakeLocal).size()!=1||zone.getRules().getValidOffsets(onsetLocal).size()!=1)
            throw new IllegalArgumentException("These times are ambiguous because of a clock change.");
        ZonedDateTime wake=wakeLocal.atZone(zone), onset=onsetLocal.atZone(zone);
        double hours=Duration.between(onset,wake).toMillis()/3600000.0;
        double rating=Double.parseDouble(score.trim());
        if(wake.isAfter(now)||hours<=0||hours>=24||!Double.isFinite(rating)||rating<0||rating>100)
            throw new IllegalArgumentException("Use a wake time before now, different sleep/wake times and a score from 0 to 100.");
        return new JSONObject().put("date",day.toString()).put("bedtime",JSONObject.NULL)
            .put("sleep_onset",onset.toOffsetDateTime().toString()).put("wake_time",wake.toOffsetDateTime().toString())
            .put("sleep_duration",hours).put("sleep_score",rating).put("sleep_regularity",JSONObject.NULL)
            .put("notes","Entered on Android; bedtime unknown. Duration is onset-to-wake, without subtracting night awakenings.");
    }
}
