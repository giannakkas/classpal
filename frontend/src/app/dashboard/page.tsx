'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/layout/AppShell';
import { api } from '@/lib/api';
import type { DashboardStats } from '@/types';
import { Camera, FileText, BookOpen, Users, Loader2 } from 'lucide-react';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<DashboardStats>('/api/dashboard/stats')
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-sm text-gray-500 mt-1">Overview of your grading activity</p>
          </div>
          <Link
            href="/scan"
            className="flex items-center gap-2 bg-brand-600 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-brand-700 transition-colors shadow-lg shadow-brand-600/20"
          >
            <Camera className="w-4 h-4" />
            Scan Paper
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
          </div>
        ) : stats ? (
          <>
            {/* Stats grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: 'Graded Today', value: stats.papers_graded_today, icon: FileText, color: 'text-green-600 bg-green-50' },
                { label: 'Pending Review', value: stats.papers_pending, icon: Camera, color: 'text-amber-600 bg-amber-50' },
                { label: 'Classes', value: stats.total_classes, icon: BookOpen, color: 'text-brand-600 bg-brand-50' },
                { label: 'Students', value: stats.total_students, icon: Users, color: 'text-purple-600 bg-purple-50' },
              ].map((stat) => (
                <div key={stat.label} className="bg-white rounded-xl border p-5">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${stat.color}`}>
                      <stat.icon className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                      <p className="text-xs text-gray-500">{stat.label}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Recent papers */}
            <div className="bg-white rounded-xl border">
              <div className="px-5 py-4 border-b">
                <h2 className="text-base font-semibold text-gray-900">Recent Papers</h2>
              </div>
              {stats.recent_papers.length === 0 ? (
                <div className="px-5 py-12 text-center text-sm text-gray-500">
                  No papers yet.{' '}
                  <Link href="/scan" className="text-brand-600 hover:underline">
                    Scan your first paper
                  </Link>
                </div>
              ) : (
                <div className="divide-y">
                  {stats.recent_papers.map((paper) => (
                    <Link
                      key={paper.id}
                      href={`/review/${paper.id}`}
                      className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${
                          paper.status === 'finalized' ? 'bg-green-500' :
                          paper.status === 'failed' ? 'bg-red-500' :
                          paper.status === 'reviewed' ? 'bg-amber-500' :
                          'bg-gray-300'
                        }`} />
                        <span className="text-sm text-gray-700">Paper #{paper.id.slice(0, 8)}</span>
                        <span className="text-xs text-gray-400 capitalize">{paper.status}</span>
                      </div>
                      <div className="text-sm">
                        {paper.score != null && paper.max_score != null ? (
                          <span className="font-medium text-gray-900">
                            {paper.score}/{paper.max_score}
                          </span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <p className="text-gray-500">Failed to load dashboard.</p>
        )}
      </div>
    </AppShell>
  );
}
