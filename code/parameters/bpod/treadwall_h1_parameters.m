%% Parameters for treadwall_habituation_1 (longer stimulus duration)
% Loaded by treadwall_habituation_1.m via treadwall_paramsdir().

% -------- Behaviour --------
STIM_DUR = 200;                                        % s, stimulus duration
ITI_DUR = 15;                                          % s, inter-trial interval
WAVEFORMS = {0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5};  % V per distance step
INIT_SCALING_FACTOR = 1;                               % initial wall-sync scaling factor
WAVE_BUFFER = 5;                                       % s, extra waveform length added beyond stimDur

% -------- Hardware --------
WAVEPLAYER_TRIGGER_MODE = 'Master';                    % Bpod WavePlayer trigger mode
STOP_CAMERA_DELAY = 1;                                 % s, BNC1 pulse hold that stops the camera
