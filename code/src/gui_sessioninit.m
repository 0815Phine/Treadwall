function gui_sessioninit(ipc_dir)
% Prepare the IPC directory at the start of a protocol: make sure it exists and
% clear any stale emergency-stop flag left over from a previous session so it
% cannot immediately abort this one.
if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
estop_flag = fullfile(ipc_dir, 'emergency_stop.flag');
if exist(estop_flag, 'file'), delete(estop_flag); end
end
