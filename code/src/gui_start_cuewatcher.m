function t = gui_start_cuewatcher(ipc_dir, gate_state, softcode, period)
% Create and start the timer that gates zone-1 start on the belt visual cue.
% Mirrors gui_start_estoptimer: a timer runs (incl. inside RunStateMachine) and,
% once the state machine enters the gate state, arms the live belt-marker detector
% (cue_arm.flag) and relays its detection (cue_detected.flag) to Bpod as a soft
% code. See cuewatch for the per-tick logic and videoacquisition.py for the detector.
%
% The caller must guard removal on every exit path, e.g.:
%   t = gui_start_cuewatcher(ipc_dir, 'waitforCue', CUE_SOFTCODE);
%   cleanupObj = onCleanup(@() stop_estoptimer(t)); %#ok<NASGU>
if nargin < 4 || isempty(period), period = 0.05; end
t = timer('Period', period, 'ExecutionMode', 'fixedRate', ...
    'UserData', struct('armed', false, 'done', false), ...
    'TimerFcn', @(src,~) cuewatch(src, ipc_dir, gate_state, softcode));
start(t);
end
