# Read-only diagnostic implementation history

Before any V2 acquisition:

1. Exact minimum-suffix-subset search passed exhaustive small set-cover tests.
2. A local read was attempted before the original archive download finished;
   no result file existed yet. No experimental condition was executed.
3. The first diagnostic attempt on the downloaded 97027028/base V1 artifact
   stopped on Windows backslash keys in artifact_hashes.json. Only the
   diagnostic manifest reader was changed to normalize separators. Original
   bytes, thresholds, V1 source and archived results were not changed.
4. The second diagnostic attempt reproduced all 1632 saved learner events,
   the final S/E, all query order, 61072 exposures and 12854 replay actions.
   It performed zero new sensor operations. Local failed output directories
   are retained. All64 diagnosis remains a required gate before V2 acquisition.

The GitHub read-only attempt at 5f86c99 may expose the same manifest-reader
error; it is not an acquisition run or a policy failure. Its logs are retained.
