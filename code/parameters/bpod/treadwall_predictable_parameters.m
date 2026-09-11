%% Parameters for treadwall_predictable
% Loaded by treadwall_predictable.m via treadwall_paramsdir().
% (Analog-in sampling rate / input range / channel count are rig hardware and
%  live in the central config: treadwall_config().bpod.analogin.)

% -------- Behaviour --------
ITI_DUR = 10;                                   % s, start-buffer / inter-trial interval
WAVEFORMS = {1.5, 2.1, 2.6, 3.2, 3.8, 4.2, 5}; % V per zone (5V = C27)
INIT_SCALING_FACTOR = 1;                        % initial wall-sync scaling factor
MAX_LAPS = 100;                                 % max trials (laps) per session
SESSION_DUR = 1200;                             % s, session timer (fires SendBpodSoftCode(1))
MAX_WAVE_DUR = 1800;                            % s, max waveform length loaded on the WavePlayer
END_BUFFER_DUR = 10;                            % s, end buffer before stopping the camera
ENCODER_THRESHOLDS = [-5, 5];                   % rotary-encoder direction thresholds
ANALOG_THRESHOLDS = [4.0, 2.5, 1.5];            % V, zone-transition thresholds (AnalogIn ch 1-3)
ANALOG_RESET_VOLTAGES = [3.2, 1.65, 1.65];      % V, threshold reset voltages (AnalogIn ch 1-3)

% -------- Hardware --------
WAVEPLAYER_TRIGGER_MODE = 'Master';             % Bpod WavePlayer trigger mode
STOP_CAMERA_DELAY = 1;                          % s, BNC1 pulse hold that stops the camera
