import engine.core.MarioAgent;
import engine.core.MarioForwardModel;
import engine.core.MarioGame;
import engine.core.MarioResult;
import engine.core.MarioTimer;
import engine.helper.MarioActions;
import java.awt.Frame;
import java.awt.Robot;
import java.awt.Rectangle;
import java.awt.Toolkit;
import java.io.*;
import java.nio.file.*;
import javax.imageio.ImageIO;
import javax.swing.JFrame;

/**
 * RGB-only MORTRA bridge.
 *
 * SNAP recaptures the currently displayed framebuffer while getActions is
 * blocked, so repeated measurements do not advance game time. STEP is the only
 * command that returns an action to the engine.
 */
public final class MortraBridge implements MarioAgent {
    private final BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
    private final PrintWriter out = new PrintWriter(System.out, true);
    private final PrintWriter trace;
    private final Path frames;
    private final boolean visuals;
    private Robot robot;
    private int tick = 0, remaining = 0, snapshot = 0;
    private boolean[] held = new boolean[MarioActions.numberOfActions()];
    private static final class Halt extends RuntimeException {}

    public MortraBridge(Path directory, boolean visuals) throws Exception {
        Files.createDirectories(directory);
        this.trace = new PrintWriter(Files.newBufferedWriter(directory.resolve("engine_frames.jsonl")));
        this.frames = directory.resolve("frames");
        this.visuals = visuals;
        if (visuals) {
            Files.createDirectories(frames);
            robot = new Robot();
        }
    }

    private Path capture() throws Exception {
        if (!visuals) throw new IllegalStateException("RGB mode requires an actual game window");
        Toolkit.getDefaultToolkit().sync();
        for (Frame frame : Frame.getFrames()) {
            if (frame.isVisible() && frame instanceof JFrame) {
                JFrame win = (JFrame) frame;
                if (!win.getTitle().equals("Mario AI Framework")) continue;
                java.awt.Component content = win.getContentPane();
                java.awt.Point p = content.getLocationOnScreen();
                Rectangle rect = new Rectangle(p.x, p.y, content.getWidth(), content.getHeight());
                Path file = frames.resolve(String.format("frame_%06d_snap_%05d.png", tick, snapshot++));
                ImageIO.write(robot.createScreenCapture(rect), "png", file.toFile());
                return file;
            }
        }
        throw new IllegalStateException("Actual game window not found");
    }

    private String observation(MarioForwardModel model, Path image) {
        return "{\"kind\":\"observation\",\"frame\":" + tick +
            ",\"snapshot\":" + (snapshot - 1) +
            ",\"status\":\"" + model.getGameStatus().toString() +
            "\",\"rgb_file\":\"" + image.toString().replace("\\", "/") + "\"}";
    }

    public void initialize(MarioForwardModel model, MarioTimer timer) {}
    public String getAgentName() { return "MORTRA-rgb-pipe"; }

    public boolean[] getActions(MarioForwardModel model, MarioTimer timer) {
        try {
            // One explicit warmup frame is counted because the window is not yet
            // rendered on the first callback.
            if (tick == 0) {
                tick++;
                trace.println("{\"warmup_frames\":1}");
                return held;
            }

            if (remaining == 0) {
                Path image = capture();
                out.println(observation(model, image));

                while (true) {
                    String line = input.readLine();
                    if (line == null || line.equals("STOP")) throw new Halt();
                    line = line.trim();
                    if (line.equals("SNAP")) {
                        Path repeated = capture();
                        String obs = observation(model, repeated);
                        trace.println("{\"snapshot_only\":" + obs + "}");
                        out.println(obs);
                        continue;
                    }

                    String[] parts = line.split("\\s+");
                    if (parts.length != 3 || !parts[0].equals("STEP"))
                        throw new IllegalArgumentException("Expected SNAP or STEP mask frame_count");
                    int mask = Integer.parseInt(parts[1]);
                    remaining = Integer.parseInt(parts[2]);
                    if (mask < 0 || mask > 31 || remaining < 1 || remaining > 12)
                        throw new IllegalArgumentException("Action outside fixed limits");
                    held = new boolean[MarioActions.numberOfActions()];
                    for (int i = 0; i < held.length; i++) held[i] = (mask & (1 << i)) != 0;
                    break;
                }
            }

            int mask = 0;
            for (int i = 0; i < held.length; i++) if (held[i]) mask |= 1 << i;
            trace.println("{\"frame\":" + tick + ",\"buttons_mask\":" + mask + "}");
            remaining--;
            tick++;
            return held;
        } catch (Halt e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 4)
            throw new IllegalArgumentException("level-file seconds output-dir visuals");
        boolean visuals = Boolean.parseBoolean(args[3]);
        MortraBridge agent = new MortraBridge(Paths.get(args[2]), visuals);
        try {
            MarioResult result = new MarioGame().runGame(
                agent, Files.readString(Paths.get(args[0])),
                Integer.parseInt(args[1]), 0, visuals, 0, 2f);
            agent.out.println("{\"kind\":\"terminal\",\"status\":\"" +
                result.getGameStatus().toString() + "\",\"frame\":" + agent.tick +
                ",\"completion_audit_only\":" + result.getCompletionPercentage() + "}");
        } catch (Halt e) {
            agent.out.println("{\"kind\":\"aborted\",\"status\":\"STOPPED_BY_RUNNER\",\"frame\":" +
                agent.tick + "}");
        } catch (Throwable e) {
            e.printStackTrace(System.err);
            agent.trace.close();
            System.exit(2);
        }
        agent.trace.close();
        System.exit(0);
    }
}
