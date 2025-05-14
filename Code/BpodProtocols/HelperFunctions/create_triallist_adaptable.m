function create_triallist_adaptable(session_dir)
% Ensure directories exist
if ~exist(session_dir, 'dir')
    mkdir(session_dir);
end

% Path for the output file
output_path = fullfile(session_dir, 'triallist.csv');

% Define trial types
offset = {'C', 'L', 'R'}; % Centre, Left, Right
distance = {'51', '45', '39', '33', '27'}; % Stimulus conditions

% Define allowed combinations as a map: key = distance, value = allowed offsets
allowed_map = containers.Map();
allowed_map('51') = offset;
allowed_map('45') = offset;
allowed_map('39') = offset;
allowed_map('33') = {'C'};  % Only allow Centre for 33
allowed_map('27') = {'C'};  % Only allow Centre for 27

% Create combinations of prefixes and angles
trial_types = {};
for i = 1:numel(distance)
    d = distance{i};
    allowed_offsets = allowed_map(d);
    for j = 1:numel(allowed_offsets)
        trial_types{end+1} = [allowed_offsets{j} d];
    end
end

% Duplicate each trial type
trial_types = repmat(trial_types, 2, 1); % Create two copies of each trial type

% Shuffle the trial list
trial_types = trial_types(randperm(numel(trial_types)));

% Write the trial list to a CSV file
fid = fopen(output_path, 'w');
fprintf(fid, 'type\n'); % Header
for i = 1:numel(trial_types)
    fprintf(fid, '%s\n', trial_types{i});
end
fclose(fid);

fprintf('Trial list saved to %s\n', output_path);
end