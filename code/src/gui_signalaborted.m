function gui_signalaborted(ipc_dir)
% Session stopped before acquisition began (e.g. emergency stop while waiting
% for WaveSurfer): the camera never triggered and captured nothing. Mark it with
% camera_no_data.flag so the GUI hard-stops/releases the camera immediately
% instead of waiting for a graceful save (and BNC stop pulse) that will never
% come and would keep the cameras busy for the next session.
%
% The marker is written BEFORE session_done.flag (inside gui_signaldone) so it
% is already present when the GUI sees session_done and decides how to stop the
% camera.
if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
fclose(fopen(fullfile(ipc_dir, 'camera_no_data.flag'), 'w'));
gui_signaldone(ipc_dir);
end
