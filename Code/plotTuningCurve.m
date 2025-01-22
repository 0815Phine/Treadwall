
data_paths = {"\\ieekf-fs1\home\timmjo\.Redirected_WinFolders\Documents\GitHub\Treadwall\Code\Arduino\Distance_Sensor\TuningCurve\sensor_data_left.xlsx",...
    "\\ieekf-fs1\home\timmjo\.Redirected_WinFolders\Documents\GitHub\Treadwall\Code\Arduino\Distance_Sensor\TuningCurve\sensor_data_right.xlsx"};
side = {'left','right'};

for sensIDX = 1:length(data_paths)
    sens_data = readtable(data_paths{sensIDX});
    sens_data = sortrows(sens_data,"Var2","ascend");

    raw_dist = sens_data.Var2;
    dist = unique(raw_dist);
    volt = horzcat(sens_data.Var3,sens_data.Var4); %sens_data.Var5,sens_data.Var6);
    volt = cellfun(@str2double, volt);

    volt_mean = zeros(length(dist), 1);
    volt_std = zeros(length(dist), 1);
    for i = 1:length(dist)
        distFlag = (dist(i) == raw_dist);

        volt_at_dist = volt(distFlag,:);
        volt_mean(i) = mean(volt_at_dist(:),'omitnan');
        volt_std(i) = std(volt_at_dist(:),'omitnan');
    end

    figure, hold on
    curve1 = volt_mean + volt_std;
    curve2 = volt_mean - volt_std;
    fill([dist; flip(dist)], [curve1' fliplr(curve2')],[0 0 .85],...
        'FaceColor','b', 'EdgeColor','none','FaceAlpha',0.2); hold on
    plot(dist,volt_mean,'LineWidth',1.5)

    xlabel('Distance (mm)'); ylabel('Output voltage (mV)')
    title(sprintf('Tuning curve for %s sensor', side{sensIDX}))
end