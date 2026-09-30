import engine.core.MarioAgent;
import engine.core.MarioForwardModel;
import engine.core.MarioGame;
import engine.core.MarioResult;
import engine.core.MarioTimer;
import engine.helper.MarioActions;

import java.awt.Frame;
import java.awt.Rectangle;
import java.awt.Robot;
import java.awt.Toolkit;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.security.MessageDigest;
import javax.swing.JFrame;

/**
 * Low-overhead RGB bridge for MORTRA.
 *
 * Fast path:
 *   screen capture -> SHA-256 -> one short JSON line.
 * No PNG, no image file, and no Python pixel transfer for an already-known
 * exact observation.
 *
 * Bulk path:
 *   DUMP / SNAPN -> persistent mmap -> NumPy/Torch.
 * SNAP and SNAPN run while getActions is blocked, so they do not advance the
 * game. STEP is the only command that advances game time.
 */
public final class MortraBridge implements MarioAgent {
    private static final int MAX_BATCH = 256;
    private static final int EDGE_PROFILE_BINS = 64;

    private final BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
    private final PrintWriter out = new PrintWriter(System.out, true);
    private final PrintWriter trace;
    private final boolean visuals;
    private final Path sharedPath;
    private final MessageDigest sha256;
    private final Robot robot;

    private RandomAccessFile sharedFile;
    private FileChannel sharedChannel;
    private MappedByteBuffer sharedMap;
    private int sharedCapacity = 0;

    private int tick = 0;
    private int remaining = 0;
    private int snapshot = 0;
    private boolean[] held = new boolean[MarioActions.numberOfActions()];
    private Captured lastCapture = null;

    private static final class Halt extends RuntimeException {}

    private static final class Captured {
        final byte[] rgb;
        final int width;
        final int height;
        final String hash;
        final long[] edgeProfile;

        Captured(byte[] rgb, int width, int height, String hash, long[] edgeProfile) {
            this.rgb = rgb;
            this.width = width;
            this.height = height;
            this.hash = hash;
            this.edgeProfile = edgeProfile;
        }
    }

    public MortraBridge(Path directory, boolean visuals, Path sharedPath) throws Exception {
        Files.createDirectories(directory);
        this.trace = new PrintWriter(Files.newBufferedWriter(directory.resolve("engine_frames.jsonl")));
        this.visuals = visuals;
        this.sharedPath = sharedPath.toAbsolutePath();
        Path parent = this.sharedPath.getParent();
        if (parent != null) Files.createDirectories(parent);
        Files.deleteIfExists(this.sharedPath);
        this.sha256 = MessageDigest.getInstance("SHA-256");
        this.robot = visuals ? new Robot() : null;
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

    private static String hex(byte[] value) {
        char[] digits = "0123456789abcdef".toCharArray();
        char[] out = new char[value.length * 2];
        for (int i = 0; i < value.length; i++) {
            int b = value[i] & 255;
            out[2*i] = digits[b >>> 4];
            out[2*i + 1] = digits[b & 15];
        }
        return new String(out);
    }

    private Captured capture() throws Exception {
        Rectangle rect = screenRect();
        BufferedImage image = robot.createScreenCapture(rect);
        int width = image.getWidth();
        int height = image.getHeight();
        int[] pixels = image.getRGB(0, 0, width, height, null, 0, width);
        byte[] rgb = new byte[width * height * 3];
        long[] edgeProfile = new long[EDGE_PROFILE_BINS];
        int k = 0;
        for (int y = 0; y < height; y++) {
            int previousR = 0, previousG = 0, previousB = 0;
            for (int x = 0; x < width; x++) {
                int value = pixels[y * width + x];
                int r = (value >>> 16) & 255;
                int g = (value >>> 8) & 255;
                int b = value & 255;
                rgb[k++] = (byte)r;
                rgb[k++] = (byte)g;
                rgb[k++] = (byte)b;
                if (x > 0) {
                    int bin = Math.min(EDGE_PROFILE_BINS - 1,
                                       x * EDGE_PROFILE_BINS / width);
                    edgeProfile[bin] += Math.abs(r - previousR)
                                      + Math.abs(g - previousG)
                                      + Math.abs(b - previousB);
                }
                previousR = r;
                previousG = g;
                previousB = b;
            }
        }
        sha256.reset();
        String hash = hex(sha256.digest(rgb));
        return new Captured(rgb, width, height, hash, edgeProfile);
    }

    private void ensureMap(int bytes) throws Exception {
        if (sharedMap != null && bytes <= sharedCapacity) return;
        if (sharedChannel != null) sharedChannel.close();
        if (sharedFile != null) sharedFile.close();

        sharedFile = new RandomAccessFile(sharedPath.toFile(), "rw");
        sharedFile.setLength(bytes);
        sharedChannel = sharedFile.getChannel();
        sharedMap = sharedChannel.map(FileChannel.MapMode.READ_WRITE, 0, bytes);
        sharedCapacity = bytes;
    }

    private void writeBatch(Captured[] frames) throws Exception {
        if (frames.length < 1 || frames.length > MAX_BATCH)
            throw new IllegalArgumentException("batch outside 1.." + MAX_BATCH);
        int width = frames[0].width;
        int height = frames[0].height;
        int frameBytes = width * height * 3;
        ensureMap(frameBytes * frames.length);
        sharedMap.position(0);
        for (Captured frame : frames) {
            if (frame.width != width || frame.height != height)
                throw new IllegalStateException("capture dimensions changed inside batch");
            sharedMap.put(frame.rgb);
        }
        // The stdout reply is emitted only after all mapped writes complete.
        // Python copies the mapped range before sending the next command.
    }

    private static String edgeProfileJson(long[] profile) {
        StringBuilder builder = new StringBuilder();
        builder.append("[");
        for (int i = 0; i < profile.length; i++) {
            if (i > 0) builder.append(",");
            builder.append(profile[i]);
        }
        builder.append("]");
        return builder.toString();
    }

    private String observationPacket(MarioForwardModel model, Captured capture) {
        return "{\"kind\":\"observation\",\"frame\":" + tick +
            ",\"snapshot\":" + (snapshot++) +
            ",\"status\":\"" + model.getGameStatus().toString() +
            "\",\"width\":" + capture.width +
            ",\"height\":" + capture.height +
            ",\"rgb_sha256\":\"" + capture.hash +
            "\",\"edge_profile\":" + edgeProfileJson(capture.edgeProfile) + "}";
    }

    private String batchPacket(MarioForwardModel model, Captured[] captures) {
        Captured first = captures[0];
        return "{\"kind\":\"observation_batch\",\"frame\":" + tick +
            ",\"snapshot\":" + (snapshot++) +
            ",\"status\":\"" + model.getGameStatus().toString() +
            "\",\"width\":" + first.width +
            ",\"height\":" + first.height +
            ",\"count\":" + captures.length +
            ",\"rgb_file\":\"" + sharedPath.toString().replace("\\", "/") + "\"}";
    }

    public void initialize(MarioForwardModel model, MarioTimer timer) {}
    public String getAgentName() { return "MORTRA-hash-mmap"; }

    public boolean[] getActions(MarioForwardModel model, MarioTimer timer) {
        try {
            // The window has not completed its first render on callback zero.
            if (tick == 0) {
                tick++;
                trace.println("{\"warmup_frames\":1}");
                return held;
            }

            if (remaining == 0) {
                lastCapture = capture();
                out.println(observationPacket(model, lastCapture));

                while (true) {
                    String line = input.readLine();
                    if (line == null || line.equals("STOP")) throw new Halt();
                    line = line.trim();

                    if (line.equals("SNAP")) {
                        Captured repeated = capture();
                        out.println(observationPacket(model, repeated));
                        continue;
                    }

                    if (line.equals("DUMP")) {
                        if (lastCapture == null) throw new IllegalStateException("no current capture");
                        Captured[] one = {lastCapture};
                        writeBatch(one);
                        out.println(batchPacket(model, one));
                        continue;
                    }

                    String[] parts = line.split("\\s+");
                    if (parts.length == 2 && parts[0].equals("SNAPN")) {
                        int count = Integer.parseInt(parts[1]);
                        if (count < 1 || count > MAX_BATCH)
                            throw new IllegalArgumentException("SNAPN outside 1.." + MAX_BATCH);
                        Captured[] batch = new Captured[count];
                        for (int i = 0; i < count; i++) batch[i] = capture();
                        writeBatch(batch);
                        out.println(batchPacket(model, batch));
                        continue;
                    }

                    if (parts.length != 3 || !parts[0].equals("STEP"))
                        throw new IllegalArgumentException(
                            "Expected SNAP, DUMP, SNAPN n, or STEP mask frame_count");

                    int mask = Integer.parseInt(parts[1]);
                    remaining = Integer.parseInt(parts[2]);
                    if (mask < 0 || mask > 31 || remaining < 1 || remaining > 12)
                        throw new IllegalArgumentException("Action outside fixed limits");
                    held = new boolean[MarioActions.numberOfActions()];
                    for (int i = 0; i < held.length; i++)
                        held[i] = (mask & (1 << i)) != 0;
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

    private void closeResources() {
        try { if (sharedChannel != null) sharedChannel.close(); } catch (Exception ignored) {}
        try { if (sharedFile != null) sharedFile.close(); } catch (Exception ignored) {}
        try { Files.deleteIfExists(sharedPath); } catch (Exception ignored) {}
        trace.close();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 5)
            throw new IllegalArgumentException(
                "level-file seconds output-dir visuals shared-mmap-file");

        boolean visuals = Boolean.parseBoolean(args[3]);
        MortraBridge agent = new MortraBridge(
            Paths.get(args[2]), visuals, Paths.get(args[4]));
        try {
            // scale=1 keeps the native 256x256 framebuffer.  The old scale=2
            // transferred 4x as many RGB bytes without adding game information.
            MarioResult result = new MarioGame().runGame(
                agent, Files.readString(Paths.get(args[0])),
                Integer.parseInt(args[1]), 0, visuals, 0, 1f);
            agent.out.println("{\"kind\":\"terminal\",\"status\":\"" +
                result.getGameStatus().toString() + "\",\"frame\":" + agent.tick +
                ",\"completion_audit_only\":" + result.getCompletionPercentage() + "}");
        } catch (Halt e) {
            agent.out.println(
                "{\"kind\":\"aborted\",\"status\":\"STOPPED_BY_RUNNER\",\"frame\":" +
                agent.tick + "}");
        } catch (Throwable e) {
            e.printStackTrace(System.err);
            agent.closeResources();
            System.exit(2);
        }
        agent.closeResources();
        System.exit(0);
    }
}
