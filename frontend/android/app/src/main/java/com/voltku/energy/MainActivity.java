package com.voltku.energy;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(VoltKuPushBridgePlugin.class);
        VoltKuNotificationHelper.ensureChannels(this);
        super.onCreate(savedInstanceState);
    }
}
