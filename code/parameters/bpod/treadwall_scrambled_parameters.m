%% Parameters for treadwall_scrambled
% Loaded by treadwall_scrambled.m via treadwall_paramsdir().

% -------- Behaviour --------
ITI_DUR = 10;                                   % s, inter-trial interval
STIM_DUR = 50;                                  % s, stimulus duration
WAVEFORMS = {1.5, 2.1, 2.6, 3.2, 3.8, 4.2, 5}; % V per distance step (5V = C27)
% WAVEFORMS = {1.3, 1.7, 2.1, 2.6, 3, 3.5, 3.9, 4.4, 5}; % 5V = R/L27
INIT_SCALING_FACTOR = 1;                        % initial wall-sync scaling factor

% -------- Hardware --------
WAVEPLAYER_TRIGGER_MODE = 'Normal';             % Bpod WavePlayer trigger mode
STOP_CAMERA_DELAY = 1;                          % s, BNC1 pulse hold that stops the camera
