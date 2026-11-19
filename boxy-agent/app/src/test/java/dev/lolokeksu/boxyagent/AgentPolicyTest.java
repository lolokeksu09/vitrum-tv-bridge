package dev.lolokeksu.boxyagent;

import org.junit.Test;
import static org.junit.Assert.*;

public final class AgentPolicyTest {
    @Test public void onlyOwnerPrivateRepoNameIsAllowed() {
        assertTrue(AgentPolicy.allowedRepo("lolokeksu09/boxy-private-control"));
        assertFalse(AgentPolicy.allowedRepo("another-user/boxy-private-control"));
        assertFalse(AgentPolicy.allowedRepo("lolokeksu09/../escape"));
        assertFalse(AgentPolicy.allowedRepo("lolokeksu09/repo?token=secret"));
        assertFalse(AgentPolicy.allowedRepo("lolokeksu09/repo.."));
    }

    @Test public void publicModeIsExplicitAndBoundToSingleRepo() {
        String known = AgentPolicy.PUBLIC_CONTROL_REPO;
        assertFalse(AgentPolicy.allowedControlRepo(known, false, false));
        assertTrue(AgentPolicy.allowedControlRepo(known, false, true));
        assertTrue(AgentPolicy.allowedControlRepo("lolokeksu09/my-private", true, false));
        assertFalse(AgentPolicy.allowedControlRepo("lolokeksu09/another-public", false, true));
        assertFalse(AgentPolicy.allowedControlRepo("attacker/boxy", false, true));
    }

    @Test public void noArbitraryCommandsOrPackages() {
        assertTrue(AgentPolicy.allowedCommand("home"));
        assertTrue(AgentPolicy.allowedCommand("back"));
        assertTrue(AgentPolicy.allowedCommand("youtube"));
        assertEquals("com.google.android.youtube.tv", AgentPolicy.appPackage("youtube"));
        for (String op : new String[]{"shell", "install", "screenshot", "reboot",
                "wifi", "uninstall", "input_key", "clear_data", "com.evil.app"}) {
            assertFalse(AgentPolicy.allowedCommand(op));
            assertNull(AgentPolicy.appPackage(op));
        }
    }

    @Test public void commandMustMatchDeviceVersionAndExactFieldCount() {
        String id = "11223344556677889900aabbccddeeff";
        assertTrue(AgentPolicy.exactRequest("BOXYAGENT/v1 home", 1, "home",
                id, id, 3));
        assertFalse(AgentPolicy.exactRequest("BOXYAGENT/v1 home", 2, "home",
                id, id, 3));
        assertFalse(AgentPolicy.exactRequest("BOXYAGENT/v1 home", 1, "home",
                "another-device", id, 3));
        assertFalse(AgentPolicy.exactRequest("BOXYAGENT/v1 home", 1, "home",
                id, id, 4));
        assertFalse(AgentPolicy.exactRequest("BOXYAGENT/v1 shell", 1, "shell",
                id, id, 3));
    }

    @Test public void staleAndFutureRequestsFailClosed() {
        long now = java.time.Instant.parse("2026-11-19T12:00:00Z").toEpochMilli();
        assertTrue(AgentPolicy.fresh("2026-11-19T11:59:00Z", now));
        assertFalse(AgentPolicy.fresh("2026-11-19T11:55:00Z", now));
        assertFalse(AgentPolicy.fresh("2026-11-19T12:02:00Z", now));
        assertFalse(AgentPolicy.fresh("invalid", now));
    }
}
