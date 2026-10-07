function gui_sessioninit(ipc_dir)
% Prepare the IPC directory at the start of a protocol: make sure it exists and
% clear any stale flags left over from a previous session (emergency-stop so it
% cannot immediately abort this one; belt-cue flags so a leftover cue_detected
% cannot fire zone 1 before this session's marker is seen).
if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
stale_flags = {'emergency_stop.flag', 'cue_arm.flag', 'cue_detected.flag'};
for i = 1:numel(stale_flags)
    f = fullfile(ipc_dir, stale_flags{i});
    if exist(f, 'file'), delete(f); end
end
end
