'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';
import { api } from '@/lib/api';
import type { Paper, Class, Assignment } from '@/types';
import { Camera, Upload, Loader2, X, RotateCcw, Check } from 'lucide-react';

export default function ScanPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'choose' | 'camera' | 'preview'>('choose');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [correctionStyle, setCorrectionStyle] = useState<string>('red_pen');

  // Camera refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Class/assignment context (optional)
  const [classes, setClasses] = useState<Class[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('');

  useEffect(() => {
    api.get<Class[]>('/api/classes').then(setClasses).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedClassId) {
      api.get<Assignment[]>(`/api/assignments?class_id=${selectedClassId}`)
        .then(setAssignments)
        .catch(() => {});
    } else {
      setAssignments([]);
      setSelectedAssignmentId('');
    }
  }, [selectedClassId]);

  // File upload handler
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) {
      setError('Please select a JPEG, PNG, or WebP image.');
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setMode('preview');
    setError('');
  };

  // Camera start
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setMode('camera');
    } catch (err) {
      setError('Camera access denied. Please allow camera access or upload a file instead.');
    }
  }, []);

  // Camera capture
  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) {
        const f = new File([blob], 'scan.jpg', { type: 'image/jpeg' });
        setFile(f);
        setPreview(canvas.toDataURL('image/jpeg'));
        stopCamera();
        setMode('preview');
      }
    }, 'image/jpeg', 0.92);
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  const resetScan = () => {
    stopCamera();
    setFile(null);
    setPreview(null);
    setMode('choose');
    setError('');
  };

  // Upload and process
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const extra: Record<string, string> = { correction_style: correctionStyle };
      if (selectedAssignmentId) extra.assignment_id = selectedAssignmentId;

      const paper = await api.uploadFile<Paper>('/api/papers/upload', file, extra);
      router.push(`/review/${paper.id}`);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
      setUploading(false);
    }
  };

  // Cleanup on unmount
  useEffect(() => () => stopCamera(), []);

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scan Paper</h1>
          <p className="text-sm text-gray-500 mt-1">
            Photograph or upload a student paper for AI grading
          </p>
        </div>

        {/* Step 1: Choose mode */}
        {mode === 'choose' && (
          <div className="space-y-4">
            {/* Context selectors */}
            <div className="bg-white rounded-xl border p-5 space-y-4">
              <p className="text-sm font-medium text-gray-700">Optional: Link to class & assignment</p>
              <div className="grid grid-cols-2 gap-3">
                <select
                  value={selectedClassId}
                  onChange={(e) => setSelectedClassId(e.target.value)}
                  className="px-3 py-2 border rounded-lg text-sm bg-white"
                >
                  <option value="">No class selected</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <select
                  value={selectedAssignmentId}
                  onChange={(e) => setSelectedAssignmentId(e.target.value)}
                  className="px-3 py-2 border rounded-lg text-sm bg-white"
                  disabled={!selectedClassId}
                >
                  <option value="">No assignment selected</option>
                  {assignments.map((a) => (
                    <option key={a.id} value={a.id}>{a.title}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Correction style */}
            <div className="bg-white rounded-xl border p-5">
              <p className="text-sm font-medium text-gray-700 mb-3">Correction style</p>
              <div className="flex gap-3">
                {[
                  { id: 'red_pen', label: 'Red Pen', color: 'bg-red-500' },
                  { id: 'blue_pen', label: 'Blue Pen', color: 'bg-blue-700' },
                  { id: 'pencil', label: 'Pencil', color: 'bg-gray-500' },
                ].map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setCorrectionStyle(s.id)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                      correctionStyle === s.id
                        ? 'border-brand-500 bg-brand-50 text-brand-700'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <div className={`w-3 h-3 rounded-full ${s.color}`} />
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Capture options */}
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={startCamera}
                className="flex flex-col items-center gap-3 p-8 bg-white rounded-xl border-2 border-dashed border-gray-300 hover:border-brand-400 hover:bg-brand-50 transition-colors"
              >
                <Camera className="w-10 h-10 text-brand-500" />
                <span className="text-sm font-medium text-gray-700">Use Camera</span>
              </button>

              <label className="flex flex-col items-center gap-3 p-8 bg-white rounded-xl border-2 border-dashed border-gray-300 hover:border-brand-400 hover:bg-brand-50 transition-colors cursor-pointer">
                <Upload className="w-10 h-10 text-brand-500" />
                <span className="text-sm font-medium text-gray-700">Upload Image</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={handleFileSelect}
                />
              </label>
            </div>
          </div>
        )}

        {/* Step 2: Camera viewfinder */}
        {mode === 'camera' && (
          <div className="relative bg-black rounded-xl overflow-hidden">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              className="w-full aspect-[3/4] object-cover"
            />
            {/* Guide overlay */}
            <div className="absolute inset-8 border-2 border-white/40 rounded-lg pointer-events-none" />

            <div className="absolute bottom-6 left-0 right-0 flex justify-center gap-4">
              <button
                onClick={resetScan}
                className="w-12 h-12 rounded-full bg-white/20 backdrop-blur flex items-center justify-center"
              >
                <X className="w-6 h-6 text-white" />
              </button>
              <button
                onClick={capturePhoto}
                className="w-16 h-16 rounded-full bg-white flex items-center justify-center shadow-xl"
              >
                <div className="w-14 h-14 rounded-full border-4 border-brand-500" />
              </button>
            </div>
            <canvas ref={canvasRef} className="hidden" />
          </div>
        )}

        {/* Step 3: Preview & confirm */}
        {mode === 'preview' && preview && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border overflow-hidden">
              <img src={preview} alt="Scanned paper" className="w-full" />
            </div>
            <div className="flex gap-3">
              <button
                onClick={resetScan}
                className="flex-1 flex items-center justify-center gap-2 py-3 border rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                <RotateCcw className="w-4 h-4" />
                Retake
              </button>
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="flex-1 flex items-center justify-center gap-2 py-3 bg-brand-600 text-white rounded-xl text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {uploading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {uploading ? 'Processing...' : 'Grade This Paper'}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
        )}
      </div>
    </AppShell>
  );
}
