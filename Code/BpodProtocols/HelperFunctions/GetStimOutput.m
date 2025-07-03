% Helper function to determine the correct stimulus output based on trial type
% this outputs are currently calibrated for my guiding plate, they might have to be adapted

function stimOutput = GetStimOutput(trialType)
    switch trialType
        %centered
        case 'C51'
            stimOutput = ['>' 2 2 255 255];
        case 'C45'
            stimOutput = ['>' 3 3 255 255]; %['!' 3 18 130];
        case 'C39'
            stimOutput = ['>' 4 4 255 255]; %['!' 3  34 155];
        case 'C33'
            stimOutput = ['>' 5 5 255 255]; %['!' 3 181 194];
        case 'C27'
            stimOutput = ['>' 6 6 255 255]; %['!' 3 205 210];
        %left
        case 'L51'
            stimOutput = ['>' 0 4 255 255];
        case 'L45'
            stimOutput = ['>' 1 5 255 255];
        case 'L39'
            stimOutput = ['>' 2 6 255 255];
        %right
        case 'R51'
            stimOutput = ['>' 4 0 255 255];
        case 'R45'
            stimOutput = ['>' 5 1 255 255];
        case 'R39'
            stimOutput = ['>' 6 2 255 255];

        % not calibrated
        case 'L33'
            stimOutput = ['>' 3 0 255 255];
        case 'L27'
            stimOutput = ['>' 4 0 255 255];
        case 'R33'
            stimOutput = ['>' 0 3 255 255];
        case 'R27'
            stimOutput = ['>' 0 4 255 255];
            
        otherwise
            error('Unknown trial type: %s', trialType);
    end
end