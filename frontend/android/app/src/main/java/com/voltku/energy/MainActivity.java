package com.voltku.energy;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(VoltKuPushBridgePlugin.class);
        super.onCreate(savedInstanceState);
        VoltKuNotificationHelper.ensureChannels(this);
    }
}
