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
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import javax.swing.JFrame;

/**
 * RGB-only MORTRA bridge.
 *
 * Performance rules:
 * - STEP is the only command that advances game time.
 * - SNAP / SNAPN recapture while getActions is blocked.
 * - RGB is written uncompressed, avoiding PNG compression/decompression.
 * - SNAPN writes a whole repeated-observation batch in one command/file.
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

    private static final class Capture {
        final Path path;
        final int width, height, count;
        Capture(Path path, int width, int height, int count) {
            this.path = path; this.width = width; this.height = height; this.count = count;
        }
    }

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

    private Rectangle screenRect() throws Exception {
        if (!visuals) throw new IllegalStateException("RGB mode requires an actual game window");
        Toolkit.getDefaultToolkit().sync();
        for (Frame frame : Frame.getFrames()) {
            if (frame.isVisible() && frame instanceof JFrame) {
                JFrame win = (JFrame) frame;
                if (!win.getTitle().equals("Mario AI Framework")) continue;
                java.awt.Component content = win.getContentPane();
                java.awt.Point p = content.getLocationOnScreen();
                return new Rectangle(p.x, p.y, content.getWidth(), content.getHeight());
            }
        }
        throw new IllegalStateException("Actual game window not found");
    }

    private static void writeRGB(BufferedImage image, OutputStream stream, byte[] row) throws Exception {
        int width = image.getWidth();
        for (int y = 0; y < image.getHeight(); y++) {
            int k = 0;
            for (int x = 0; x < width; x++) {
                int rgb = image.getRGB(x, y);
                row[k++] = (byte)((rgb >>> 16) & 255);
                row[k++] = (byte)((rgb >>> 8) & 255);
                row[k++] = (byte)(rgb & 255);
            }
            stream.write(row, 0, k);
        }
    }

    private Capture captureBatch(int count) throws Exception {
        if (count < 1 || count > 2048) throw new IllegalArgumentException("SNAPN count outside 1..2048");
        Rectangle rect = screenRect();
        int id = snapshot++;
        Path file = frames.resolve(String.format("rgb_%06d_%05d_%04d.raw", tick, id, count));
        byte[] row = new byte[rect.width * 3];
        try (OutputStream stream = new BufferedOutputStream(
                Files.newOutputStream(file, StandardOpenOption.CREATE_NEW), 1 << 20)) {
            for (int i = 0; i < count; i++) {
                Toolkit.getDefaultToolkit().sync();
                BufferedImage image = robot.createScreenCapture(rect);
                writeRGB(image, stream, row);
            }
        }
        return new Capture(file, rect.width, rect.height, count);
    }

    private String packet(String kind, MarioForwardModel model, Capture capture) {
        return "{\"kind\":\"" + kind + "\",\"frame\":" + tick +
            ",\"snapshot\":" + (snapshot - 1) +
            ",\"status\":\"" + model.getGameStatus().toString() +
            "\",\"rgb_file\":\"" + capture.path.toString().replace("\\", "/") +
            "\",\"width\":" + capture.width +
            ",\"height\":" + capture.height +
            ",\"count\":" + capture.count + "}";
    }

    public void initialize(MarioForwardModel model, MarioTimer timer) {}
    public String getAgentName() { return "MORTRA-rgb-raw-pipe"; }

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
                Capture image = captureBatch(1);
                out.println(packet("observation", model, image));

                while (true) {
                    String line = input.readLine();
                    if (line == null || line.equals("STOP")) throw new Halt();
                    line = line.trim();
                    if (line.equals("SNAP")) {
                        Capture repeated = captureBatch(1);
                        String obs = packet("observation", model, repeated);
                        trace.println("{\"snapshot_only\":" + obs + "}");
                        out.println(obs);
                        continue;
                    }

                    String[] parts = line.split("\\s+");
                    if (parts.length == 2 && parts[0].equals("SNAPN")) {
                        int count = Integer.parseInt(parts[1]);
                        Capture repeated = captureBatch(count);
                        String obs = packet("observation_batch", model, repeated);
                        trace.println("{\"snapshot_batch_count\":" + count +
                                      ",\"frame\":" + tick + "}");
                        out.println(obs);
                        continue;
                    }

                    if (parts.length != 3 || !parts[0].equals("STEP"))
                        throw new IllegalArgumentException("Expected SNAP, SNAPN n, or STEP mask frame_count");
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
