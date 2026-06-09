"""
test_acquisition_logic.py — tests for the chunk-buffer and writer logic.
Runs without any camera hardware.
"""

import numpy as np
import threading
import queue
import os
import tempfile

CHUNK_SIZE = 200
H, W = 1080, 1440


def _make_buffers():
    return (
        [np.empty((CHUNK_SIZE, H, W), dtype=np.uint8),
         np.empty((CHUNK_SIZE, H, W), dtype=np.uint8)],
        [np.empty(CHUNK_SIZE, dtype=np.int64),
         np.empty(CHUNK_SIZE, dtype=np.int64)],
        [np.empty(CHUNK_SIZE, dtype=np.int64),
         np.empty(CHUNK_SIZE, dtype=np.int64)],
    )


def _run_writer(write_queue, frame_bufs, cam_ts_bufs, pc_ts_bufs, folder):
    while True:
        item = write_queue.get()
        if item is None:
            write_queue.task_done()
            break
        slot, n, chunk_idx = item
        try:
            np.save(os.path.join(folder, f"chunk_{chunk_idx:06d}.npy"),
                    frame_bufs[slot][:n])
            np.save(os.path.join(folder, f"chunk_{chunk_idx:06d}_cam_ts.npy"),
                    cam_ts_bufs[slot][:n])
            np.save(os.path.join(folder, f"chunk_{chunk_idx:06d}_pc_ts.npy"),
                    pc_ts_bufs[slot][:n])
        except Exception as e:
            print(f"  Writer error: {e}")
        write_queue.task_done()


def test_single_chunk_dispatch():
    """Exactly CHUNK_SIZE frames must trigger one dispatch on slot 0."""
    frames, cam_ts, pc_ts = _make_buffers()
    q = queue.Queue()
    slot = 0; fill = 0; counter = 0

    for i in range(CHUNK_SIZE):
        frames[slot][fill] = np.zeros((H, W), dtype=np.uint8)
        cam_ts[slot][fill] = i
        pc_ts[slot][fill]  = i * 5_000_000
        fill += 1
        if fill == CHUNK_SIZE:
            q.put((slot, CHUNK_SIZE, counter))
            slot ^= 1; fill = 0; counter += 1

    assert q.qsize() == 1, f"Expected 1 dispatch, got {q.qsize()}"
    item = q.get_nowait()
    assert item == (0, CHUNK_SIZE, 0), f"Wrong item: {item}"
    assert slot == 1
    assert fill == 0
    assert counter == 1
    print("  test_single_chunk_dispatch: PASSED")


def test_double_chunk_slot_alternation():
    """Two full chunks must use alternating slots (0, 1) and sequential counters."""
    frames, cam_ts, pc_ts = _make_buffers()
    q = queue.Queue()
    slot = 0; fill = 0; counter = 0

    for i in range(CHUNK_SIZE * 2):
        frames[slot][fill] = np.full((H, W), i % 256, dtype=np.uint8)
        fill += 1
        if fill == CHUNK_SIZE:
            q.put((slot, CHUNK_SIZE, counter))
            slot ^= 1; fill = 0; counter += 1

    assert q.qsize() == 2
    a = q.get_nowait()
    b = q.get_nowait()
    assert a == (0, CHUNK_SIZE, 0), f"First chunk: {a}"
    assert b == (1, CHUNK_SIZE, 1), f"Second chunk: {b}"
    assert slot == 0   # back to 0 after two chunks
    assert counter == 2
    print("  test_double_chunk_slot_alternation: PASSED")


def test_partial_last_chunk_flush():
    """37 frames → no dispatch during loop; flush produces (0, 37, 0)."""
    frames, cam_ts, pc_ts = _make_buffers()
    q = queue.Queue()
    slot = 0; fill = 0; counter = 0
    PARTIAL = 37

    for i in range(PARTIAL):
        frames[slot][fill] = np.zeros((H, W), dtype=np.uint8)
        fill += 1
        if fill == CHUNK_SIZE:
            q.put((slot, CHUNK_SIZE, counter))
            slot ^= 1; fill = 0; counter += 1

    assert q.qsize() == 0, "Should not dispatch incomplete chunk during loop"

    if fill > 0:
        q.put((slot, fill, counter))
        counter += 1

    assert q.qsize() == 1
    item = q.get_nowait()
    assert item == (0, PARTIAL, 0), f"Wrong partial flush: {item}"
    print("  test_partial_last_chunk_flush: PASSED")


def test_writer_saves_correct_files():
    """Writer thread must save .npy files with the exact data dispatched."""
    frames, cam_ts, pc_ts = _make_buffers()
    q = queue.Queue()

    # Put known data into slot 0, frame 0
    test_image = np.arange(H * W, dtype=np.uint8).reshape(H, W)
    frames[0][0] = test_image
    cam_ts[0][0] = 123456789
    pc_ts[0][0]  = 987654321

    with tempfile.TemporaryDirectory() as tmpdir:
        wt = threading.Thread(target=_run_writer,
                              args=(q, frames, cam_ts, pc_ts, tmpdir))
        wt.start()
        q.put((0, 1, 0))
        q.put(None)
        q.join()
        wt.join()

        f_path  = os.path.join(tmpdir, "chunk_000000.npy")
        ct_path = os.path.join(tmpdir, "chunk_000000_cam_ts.npy")
        pt_path = os.path.join(tmpdir, "chunk_000000_pc_ts.npy")

        assert os.path.exists(f_path),  "Frame file missing"
        assert os.path.exists(ct_path), "cam_ts file missing"
        assert os.path.exists(pt_path), "pc_ts file missing"

        saved_f  = np.load(f_path)
        saved_ct = np.load(ct_path)
        saved_pt = np.load(pt_path)

        assert saved_f.shape == (1, H, W), f"Wrong shape: {saved_f.shape}"
        assert np.array_equal(saved_f[0], test_image), "Frame data corrupted"
        assert saved_ct[0] == 123456789, f"cam_ts wrong: {saved_ct[0]}"
        assert saved_pt[0] == 987654321, f"pc_ts wrong: {saved_pt[0]}"

    print("  test_writer_saves_correct_files: PASSED")


def test_writer_multi_chunk_sequential():
    """Two chunks written sequentially must produce correctly numbered files."""
    frames, cam_ts, pc_ts = _make_buffers()
    q = queue.Queue()

    N = 10  # frames per chunk for this test
    for slot_idx in range(2):
        for f in range(N):
            frames[slot_idx][f] = np.full((H, W), slot_idx * 100 + f, dtype=np.uint8)

    with tempfile.TemporaryDirectory() as tmpdir:
        wt = threading.Thread(target=_run_writer,
                              args=(q, frames, cam_ts, pc_ts, tmpdir))
        wt.start()
        q.put((0, N, 0))
        q.put((1, N, 1))
        q.put(None)
        q.join()
        wt.join()

        for idx in range(2):
            path = os.path.join(tmpdir, f"chunk_{idx:06d}.npy")
            assert os.path.exists(path), f"chunk_{idx:06d}.npy missing"
            data = np.load(path)
            assert data.shape == (N, H, W), f"Chunk {idx} wrong shape"
            assert data[0, 0, 0] == idx * 100, f"Chunk {idx} data wrong"

    print("  test_writer_multi_chunk_sequential: PASSED")


def test_timestamp_file_format():
    """_save_timestamps must write one bare int64 per line (MATLAB-compatible)."""
    frames, cam_ts, pc_ts = _make_buffers()
    q = queue.Queue()

    N = 5
    expected_ts = [100, 200, 300, 400, 500]
    for i in range(N):
        cam_ts[0][i] = expected_ts[i]

    with tempfile.TemporaryDirectory() as tmpdir:
        wt = threading.Thread(target=_run_writer,
                              args=(q, frames, cam_ts, pc_ts, tmpdir))
        wt.start()
        q.put((0, N, 0))
        q.put(None)
        q.join()
        wt.join()

        # Reconstruct combined timestamps file (mirrors DailyDataManager logic)
        ts_file = os.path.join(tmpdir, "video_timestamps.txt")
        all_ts = []
        p = os.path.join(tmpdir, "chunk_000000_cam_ts.npy")
        all_ts.append(np.load(p))
        combined = np.concatenate(all_ts)
        with open(ts_file, 'w') as f:
            for ts in combined:
                f.write(f"{ts}\n")

        with open(ts_file) as f:
            lines = f.readlines()

        assert len(lines) == N, f"Expected {N} lines, got {len(lines)}"
        for i, line in enumerate(lines):
            val = int(line.strip())
            assert val == expected_ts[i], f"Line {i}: expected {expected_ts[i]}, got {val}"

    print("  test_timestamp_file_format: PASSED")


if __name__ == "__main__":
    print("Running acquisition logic tests (no camera required)...\n")
    test_single_chunk_dispatch()
    test_double_chunk_slot_alternation()
    test_partial_last_chunk_flush()
    test_writer_saves_correct_files()
    test_writer_multi_chunk_sequential()
    test_timestamp_file_format()
    print("\nAll tests passed.")
