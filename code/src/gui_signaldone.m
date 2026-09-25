function gui_signaldone(ipc_dir)
% Signal the GUI that the session is complete and tell WaveSurfer to stop/rename.
% Also clears the live-state report so the GUI shows idle between sessions.
% Safe to call on both the normal end and the "stopped while waiting for
% WaveSurfer" early-exit path.
if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
fclose(fopen(fullfile(ipc_dir, 'stop_wavesurfer.flag'), 'w'));
fclose(fopen(fullfile(ipc_dir, 'session_done.flag'), 'w'));
state_file = fullfile(ipc_dir, 'bpod_state.txt');
if exist(state_file, 'file'), delete(state_file); end
end
