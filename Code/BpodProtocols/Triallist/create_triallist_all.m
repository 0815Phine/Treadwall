function create_triallist_all(start_path, animal_id, session_id)
% Ensure directories exist
animal_dir = fullfile(start_path, animal_id);
session_dir = fullfile(animal_dir, session_id);
if ~exist(session_dir, 'dir')
    mkdir(session_dir);
end

% Path for the output file
output_path = fullfile(session_dir, 'triallist.csv');

% Define trial types
offset = {'C', 'L', 'R'}; % Centre, Left, Right
distance = {'45', '39', '33', '27'}; % Stimulus conditions

% Create combinations of prefixes and angles
trial_types = cell(numel(offset) * numel(distance), 1);
idx = 1;
for p = 1:numel(offset)
    for a = 1:numel(distance)
        trial_types{idx} = [offset{p} distance{a}];
        idx = idx + 1;
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