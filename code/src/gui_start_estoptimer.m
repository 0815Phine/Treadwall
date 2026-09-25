function t = gui_start_estoptimer(ipc_dir)
% Create and start the 0.5 s watcher timer that reports the live Bpod state to
% the GUI and handles the emergency-stop flag (see reportandcheck). Polling
% from a timer means the GUI emergency-stop button works even while the protocol
% is blocked waiting for WaveSurfer.
%
% The caller must guard removal on every exit path, e.g.:
%   t = gui_start_estoptimer(ipc_dir);
%   cleanupObj = onCleanup(@() stop_estoptimer(t)); %#ok<NASGU>
t = timer('Period', 0.5, 'ExecutionMode', 'fixedRate', ...
    'TimerFcn', @(~,~) reportandcheck(ipc_dir));
start(t);
end
