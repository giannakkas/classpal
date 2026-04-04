'use client';

import { useEffect, useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { api } from '@/lib/api';
import type { Class, Student } from '@/types';
import { Plus, BookOpen, Users, Loader2, Trash2 } from 'lucide-react';

export default function ClassesPage() {
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [subject, setSubject] = useState('');
  const [gradeLevel, setGradeLevel] = useState('');
  const [creating, setCreating] = useState(false);

  const load = () => {
    api.get<Class[]>('/api/classes')
      .then(setClasses)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post('/api/classes', { name, subject: subject || null, grade_level: gradeLevel || null });
      setName(''); setSubject(''); setGradeLevel('');
      setShowCreate(false);
      load();
    } catch (err: any) {
      alert(err.message);
    }
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this class?')) return;
    try {
      await api.delete(`/api/classes/${id}`);
      load();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Classes</h1>
            <p className="text-sm text-gray-500 mt-1">Manage your classes and students</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700"
          >
            <Plus className="w-4 h-4" />
            New Class
          </button>
        </div>

        {/* Create form */}
        {showCreate && (
          <form onSubmit={handleCreate} className="bg-white rounded-xl border p-5 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <input
                type="text"
                required
                placeholder="Class name (e.g. Year 5 Maths)"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm col-span-1"
              />
              <input
                type="text"
                placeholder="Subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm"
              />
              <input
                type="text"
                placeholder="Grade level"
                value={gradeLevel}
                onChange={(e) => setGradeLevel(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Class'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Class list */}
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
          </div>
        ) : classes.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border">
            <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No classes yet. Create your first class to get started.</p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {classes.map((cls) => (
              <div key={cls.id} className="bg-white rounded-xl border p-5 hover:shadow-sm transition-shadow">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{cls.name}</h3>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {[cls.subject, cls.grade_level].filter(Boolean).join(' · ') || 'No details'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(cls.id)}
                    className="p-1 text-gray-400 hover:text-red-500"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
                  <Users className="w-4 h-4" />
                  {cls.student_count} students
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
