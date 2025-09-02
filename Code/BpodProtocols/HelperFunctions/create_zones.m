function zones_path = create_zones(animal_dir)
% Ensure directories exist
if ~exist(animal_dir, 'dir')
    mkdir(animal_dir);
end

% Path for the output file
zones_path = fullfile(animal_dir, 'zones.csv');

% Define trial types
offset = {'C', 'L', 'R'}; % Centre, Left, Right
distance = {'51', '45', '39', '33', '27'}; % Stimulus conditions

sel_distance = randsample(distance, 4);

% Define allowed combinations as a map: key = distance, value = allowed offsets
allowed_map = containers.Map();
allowed_map('51') = offset;
allowed_map('45') = offset;
allowed_map('39') = offset;
allowed_map('33') = {'C'};  % Only allow Centre for 33
allowed_map('27') = {'C'};  % Only allow Centre for 27

% Create combinations of prefixes and angles
zones = cell(1,4);
for i = 1:4
    d = sel_distance{i};
    allowed_offsets = allowed_map(d);
    chosen_offset = allowed_offsets{randi(numel(allowed_offsets))};
    zones{i} = [chosen_offset d];
end

% Write the trial list to a CSV file
fid = fopen(zones_path, 'w');
fprintf(fid, 'type\n'); % Header
for i = 1:numel(zones)
    fprintf(fid, '%s\n', zones{i});
end
fclose(fid);

fprintf('Zones for this animal saved to %s\n', zones_path);
