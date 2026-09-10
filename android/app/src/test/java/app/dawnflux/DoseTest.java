package app.dawnflux;
import org.junit.Test;
import static org.junit.Assert.*;

public class DoseTest {
    @Test public void irregularTrapezoid() {
        Dose d=new Dose(); d.add(0,100); d.add(60_000,300); d.add(180_000,500);
        assertEquals(1000,d.total,1e-9); assertFalse(d.gapped);
    }
    @Test public void longGapIsNotExposure() {
        Dose d=new Dose(); d.add(0,100); d.add(60_000,100); d.add(660_000,100);
        assertEquals(100,d.total,1e-9); assertTrue(d.gapped);
    }
    @Test public void duplicateAndOutOfOrderIgnored() {
        Dose d=new Dose(); d.add(2000,500); assertFalse(d.add(2000,900)); assertFalse(d.add(1000,900)); assertEquals(0,d.total,0);
    }
    @Test(expected=IllegalArgumentException.class) public void invalidLuxRejected() { new Dose().add(0,Double.NaN); }
    @Test public void zeroLuxAndTargetBoundary() {
        Dose d=new Dose(); d.add(0,0); d.add(60_000,200); assertEquals(100,d.total,0);
    }
}
