% Helper function to determine the correct stimulus output based on trial type
function stimOutput = GetStimOutput(trialType)
    switch trialType
        case 'C51'
            stimOutput = ['>' 9 3 255 255];
        case 'C45'
            stimOutput = ['>' 10 4 255 255]; %['!' 3 18 130];
        case 'C39'
            stimOutput = ['>' 11 5 255 255]; %['!' 3  34 155];
        case 'C33'
            stimOutput = ['>' 12 6 255 255]; %['!' 3 181 194];
        case 'C27'
            stimOutput = ['>' 13 13 255 255]; %['!' 3 205 210];
        case 'L51'
            stimOutput = ['>' 7 5 255 255];
        case 'L45'
            stimOutput = ['>' 8 6 255 255];
        case 'L39'
            stimOutput = ['>' 9 7 255 255];
        % case 'L33'
        %     stimOutput = ['>' 3 7 255 255];
        % case 'L27'
        %     stimOutput = ['>' 4 8 255 255];
        case 'R51'
            stimOutput = ['>' 11 1 255 255];
        case 'R45'
            stimOutput = ['>' 12 2 255 255];
        case 'R39'
            stimOutput = ['>' 13 3 255 255];
        % case 'R33'
        %     stimOutput = ['>' 7 3 255 255];
        % case 'R27'
        %     stimOutput = ['>' 8 4 255 255];
        otherwise
            error('Unknown trial type: %s', trialType);
    end
end