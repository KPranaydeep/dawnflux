package app.dawnflux;

import org.junit.Test;
import static org.junit.Assert.*;

public class EtaTest {
    @Test public void remainingDoseDividedByLux() {
        assertEquals("ETA: about 10 min 0 sec at current light", Eta.label(5000,10000,500,true,true));
        assertEquals("ETA: about 5 min 0 sec at current light", Eta.label(5000,10000,1000,true,true));
        assertEquals("ETA: about 30 sec at current light", Eta.label(9500,10000,1000,true,true));
    }
    @Test public void darknessStalenessAndPoorQualityHaveNoEstimate() {
        assertEquals("ETA: waiting for light", Eta.label(0,10000,0,true,true));
        assertEquals("ETA: waiting for fresh readings", Eta.label(0,10000,500,false,true));
        assertEquals("ETA unavailable · check sensor", Eta.label(0,10000,500,true,false));
        assertEquals("ETA unavailable · check sensor", Eta.label(0,10000,Double.NaN,true,true));
    }
    @Test public void reachedTargetNeverHasNegativeTime() {
        assertEquals("ETA: 0 sec · target reached", Eta.label(10000,10000,0,false,false));
        assertEquals("ETA: 0 sec · target reached", Eta.label(12000,10000,500,true,true));
    }
    @Test public void extremeLowLightDoesNotOverflow() {
        assertEquals("ETA: more than 24 hours at current light", Eta.label(0,10000,Double.MIN_VALUE,true,true));
    }
    @Test public void positiveRemainderRoundsUp() {
        assertEquals("ETA: about 1 sec at current light", Eta.label(9999.99,10000,1000,true,true));
    }
}
