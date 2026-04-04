'use client';

import { AppShell } from '@/components/layout/AppShell';
import { useAuthStore } from '@/stores/auth';

export default function SettingsPage() {
  const { user } = useAuthStore();

  return (
    <AppShell>
      <div className="space-y-6 max-w-2xl">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your account and preferences</p>
        </div>

        <div className="bg-white rounded-xl border divide-y">
          <div className="p-5">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Account</h3>
            <div className="space-y-2 text-sm">
              <p><span className="text-gray-500">Name:</span> <span className="font-medium">{user?.full_name}</span></p>
              <p><span className="text-gray-500">Email:</span> <span className="font-medium">{user?.email}</span></p>
              <p><span className="text-gray-500">Plan:</span> <span className="font-medium capitalize">{user?.subscription_tier}</span></p>
            </div>
          </div>

          <div className="p-5">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Default Correction Style</h3>
            <div className="flex gap-3">
              {['red_pen', 'blue_pen', 'pencil'].map((s) => (
                <div
                  key={s}
                  className={`px-4 py-2 rounded-lg border text-sm capitalize ${
                    user?.preferred_correction_style === s
                      ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium'
                      : 'text-gray-500'
                  }`}
                >
                  {s.replace('_', ' ')}
                </div>
              ))}
            </div>
          </div>

          <div className="p-5">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Subscription</h3>
            <p className="text-sm text-gray-600 mb-3">
              Manage your subscription and billing details.
            </p>
            <button className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50">
              Manage Billing
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
