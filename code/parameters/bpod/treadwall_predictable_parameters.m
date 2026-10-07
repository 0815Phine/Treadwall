%% Parameters for treadwall_predictable
% Loaded by treadwall_predictable.m via treadwall_paramsdir().
% (Analog-in sampling rate / input range / channel count are rig hardware and
%  live in the central config: treadwall_config().bpod.analogin.)

% -------- Behaviour --------
ITI_DUR = 5;                                   % s, start-buffer / inter-trial interval
WAVEFORMS = {1.5, 2.1, 2.6, 3.2, 3.8, 4.2, 5}; % V per zone (5V = C27)
INIT_SCALING_FACTOR = 1;                        % initial wall-sync scaling factor
MAX_LAPS = 100;                                 % max trials (laps) per session
SESSION_DUR = 1800;                             % s, session timer (fires SendBpodSoftCode(1))
MAX_WAVE_DUR = 2000;                            % s, max waveform length loaded on the WavePlayer
END_BUFFER_DUR = 10;                            % s, end buffer before stopping the camera
ENCODER_THRESHOLDS = [-5, 5];                   % rotary-encoder direction thresholds

% -------- Visual-cue zone-1 start (trial 1 only) --------
% Gate the first zone on the belt's visual marker so zone 1 always starts at the
% same belt position across sessions. The marker is detected live from the top
% camera (code/src/videoacquisition.py) and relayed to Bpod as a soft code via
% the cue-watcher timer (gui_start_cuewatcher.m). See the plan/README for details.
USE_CUE_START = true;                           % master on/off (per-session knob)
CUE_SOFTCODE = 3;                               % soft code relaying the cue (1,2 taken)
CUE_TIMEOUT = 120;                               % s, fallback: start on first trigger if no cue
CUE_TRIGGER_OFFSET = 1;                          % zone 1 starts on the Nth trigger after the cue
N_ACTIVE_CHAN = 3;
ANALOG_THRESHOLDS = [4.0, 2.5, 1.5];            % V, zone-transition thresholds (AnalogIn ch 1-3)
ANALOG_RESET_VOLTAGES = [3.2, 1.65, 1.65];      % V, threshold reset voltages (AnalogIn ch 1-3)

% -------- Hardware --------
WAVEPLAYER_TRIGGER_MODE = 'Master';             % Bpod WavePlayer trigger mode
