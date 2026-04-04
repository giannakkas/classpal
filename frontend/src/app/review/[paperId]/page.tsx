'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { Paper, Annotation, CorrectionStyle, QuestionResult } from '@/types';
import {
  Check, X, Circle, Minus, Type, Hash, Download, Printer,
  Loader2, ChevronLeft, Undo2, Redo2, ZoomIn, ZoomOut, Save,
  AlertTriangle, Eye,
} from 'lucide-react';
import { cn } from '@/lib/utils';

type Tool = 'select' | 'checkmark' | 'xmark' | 'circle' | 'underline' | 'text_note' | 'score_box';

const STYLE_COLORS: Record<CorrectionStyle, string> = {
  red_pen: '#CC2222',
  blue_pen: '#1A4B8C',
  pencil: '#4A4A4A',
};

export default function ReviewPage() {
  const { paperId } = useParams<{ paperId: string }>();
  const router = useRouter();

  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

  // Canvas state
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [activeTool, setActiveTool] = useState<Tool>('select');
  const [correctionStyle, setCorrectionStyle] = useState<CorrectionStyle>('red_pen');
  const [zoom, setZoom] = useState(1);
  const [selectedAnnotation, setSelectedAnnotation] = useState<string | null>(null);
  const [undoStack, setUndoStack] = useState<Annotation[][]>([]);
  const [redoStack, setRedoStack] = useState<Annotation[][]>([]);

  // Image
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });

  // Load paper
  useEffect(() => {
    loadPaper();
  }, [paperId]);

  const loadPaper = async () => {
    try {
      const p = await api.get<Paper>(`/api/papers/${paperId}`);
      setPaper(p);
      setCorrectionStyle(p.correction_style);

      if (p.annotations) {
        setAnnotations(p.annotations);
      }

      // If still processing, start polling
      if (['pending', 'processing'].includes(p.processing_status)) {
        setPolling(true);
      } else {
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  };

  // Poll for processing status
  useEffect(() => {
    if (!polling) return;

    const interval = setInterval(async () => {
      try {
        const status = await api.get<{ processing_status: string }>(`/api/papers/${paperId}/status`);
        if (!['pending', 'processing'].includes(status.processing_status)) {
          setPolling(false);
          await loadPaper();
        }
      } catch {
        setPolling(false);
        setLoading(false);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [polling, paperId]);

  // Image loaded handler
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
    setImageLoaded(true);
    setLoading(false);
  };

  // Annotation CRUD
  const pushUndo = () => {
    setUndoStack((prev) => [...prev.slice(-20), annotations]);
    setRedoStack([]);
  };

  const addAnnotation = useCallback((ann: Annotation) => {
    pushUndo();
    setAnnotations((prev) => [...prev, ann]);
  }, [annotations]);

  const removeAnnotation = (id: string) => {
    pushUndo();
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    if (selectedAnnotation === id) setSelectedAnnotation(null);
  };

  const undo = () => {
    if (undoStack.length === 0) return;
    setRedoStack((prev) => [...prev, annotations]);
    setAnnotations(undoStack[undoStack.length - 1]);
    setUndoStack((prev) => prev.slice(0, -1));
  };

  const redo = () => {
    if (redoStack.length === 0) return;
    setUndoStack((prev) => [...prev, annotations]);
    setAnnotations(redoStack[redoStack.length - 1]);
    setRedoStack((prev) => prev.slice(0, -1));
  };

  // Canvas click handler — add annotation at click position
  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool === 'select') return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    const id = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    const newAnn: Annotation = {
      id,
      type: activeTool === 'score_box' ? 'score_box' : activeTool,
      position: { x, y },
      style: correctionStyle,
      ai_generated: false,
      confidence: 1.0,
    };

    if (activeTool === 'text_note') {
      const text = prompt('Enter correction note:');
      if (!text) return;
      newAnn.text = text;
    }

    if (activeTool === 'score_box') {
      const score = prompt('Enter score (e.g. 8/10):');
      if (!score) return;
      newAnn.text = score;
    }

    addAnnotation(newAnn);
  };

  // Save annotations
  const handleSave = async () => {
    if (!paper) return;
    setSaving(true);
    try {
      const totalScore = annotations
        .filter((a) => a.type === 'checkmark' || a.type === 'xmark')
        .reduce((sum, a) => sum + (a.score ?? 0), 0);
      const maxScore = annotations
        .filter((a) => a.type === 'checkmark' || a.type === 'xmark')
        .reduce((sum, a) => sum + (a.max_score ?? 0), 0);

      const updated = await api.put<Paper>(`/api/papers/${paper.id}/annotations`, {
        annotations,
        total_score: paper.evaluation_result?.total_score ?? totalScore,
        max_score: paper.evaluation_result?.max_score ?? maxScore,
        correction_style: correctionStyle,
      });
      setPaper(updated);
    } catch (err: any) {
      alert('Save failed: ' + err.message);
    }
    setSaving(false);
  };

  // Finalize
  const handleFinalize = async () => {
    if (!paper) return;
    await handleSave();
    setFinalizing(true);
    try {
      const updated = await api.post<Paper>(`/api/papers/${paper.id}/finalize`);
      setPaper(updated);
      // Poll for PDF generation
      const pollPdf = setInterval(async () => {
        const p = await api.get<Paper>(`/api/papers/${paper.id}`);
        if (p.corrected_pdf_url) {
          clearInterval(pollPdf);
          setPaper(p);
          setFinalizing(false);
        }
      }, 2000);
    } catch (err: any) {
      alert('Finalize failed: ' + err.message);
      setFinalizing(false);
    }
  };

  // Questions from AI result
  const questions: QuestionResult[] = paper?.evaluation_result?.questions ?? [];

  const imageUrl = paper?.processed_image_url || paper?.original_image_url;

  // Rendering
  if (loading || polling) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-gray-50">
        <Loader2 className="w-10 h-10 animate-spin text-brand-500" />
        <p className="text-sm text-gray-600">
          {polling ? 'AI is analyzing the paper...' : 'Loading...'}
        </p>
        {polling && (
          <p className="text-xs text-gray-400">This usually takes 10-30 seconds</p>
        )}
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Paper not found.</p>
      </div>
    );
  }

  if (paper.processing_status === 'failed') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <AlertTriangle className="w-10 h-10 text-red-500" />
        <p className="text-red-600 font-medium">Processing failed</p>
        <p className="text-sm text-gray-500">
          {(paper.ocr_result as any)?.error || 'Unknown error'}
        </p>
        <button
          onClick={() => router.push('/scan')}
          className="mt-4 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Top bar */}
      <header className="bg-white border-b px-4 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push('/dashboard')} className="text-gray-500 hover:text-gray-700">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <h1 className="text-sm font-semibold text-gray-900">Review Paper</h1>
          <span className="text-xs px-2 py-0.5 bg-gray-100 rounded text-gray-500 capitalize">
            {paper.processing_status}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Undo / Redo */}
          <button onClick={undo} disabled={undoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30">
            <Undo2 className="w-4 h-4" />
          </button>
          <button onClick={redo} disabled={redoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30">
            <Redo2 className="w-4 h-4" />
          </button>

          <div className="w-px h-5 bg-gray-200 mx-1" />

          {/* Zoom */}
          <button onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} className="p-1.5 rounded hover:bg-gray-100">
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-xs text-gray-500 w-10 text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => Math.min(3, z + 0.25))} className="p-1.5 rounded hover:bg-gray-100">
            <ZoomIn className="w-4 h-4" />
          </button>

          <div className="w-px h-5 bg-gray-200 mx-1" />

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Save
          </button>

          {/* Finalize */}
          <button
            onClick={handleFinalize}
            disabled={finalizing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {finalizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            {finalizing ? 'Generating PDF...' : 'Finalize & Export'}
          </button>

          {/* PDF download if available */}
          {paper.corrected_pdf_url && (
            <a
              href={paper.corrected_pdf_url}
              target="_blank"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              <Download className="w-3.5 h-3.5" />
              PDF
            </a>
          )}
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Tool sidebar */}
        <aside className="w-14 bg-white border-r flex flex-col items-center py-3 gap-1 shrink-0">
          {([
            { tool: 'select' as Tool, icon: Eye, label: 'Select' },
            { tool: 'checkmark' as Tool, icon: Check, label: 'Check ✓' },
            { tool: 'xmark' as Tool, icon: X, label: 'X Mark ✗' },
            { tool: 'circle' as Tool, icon: Circle, label: 'Circle' },
            { tool: 'underline' as Tool, icon: Minus, label: 'Underline' },
            { tool: 'text_note' as Tool, icon: Type, label: 'Text Note' },
            { tool: 'score_box' as Tool, icon: Hash, label: 'Score' },
          ]).map(({ tool, icon: Icon, label }) => (
            <button
              key={tool}
              onClick={() => setActiveTool(tool)}
              title={label}
              className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center transition-colors',
                activeTool === tool ? 'bg-brand-100 text-brand-700' : 'text-gray-500 hover:bg-gray-100'
              )}
            >
              <Icon className="w-5 h-5" />
            </button>
          ))}

          <div className="w-8 h-px bg-gray-200 my-2" />

          {/* Style selector */}
          {(['red_pen', 'blue_pen', 'pencil'] as CorrectionStyle[]).map((s) => (
            <button
              key={s}
              onClick={() => setCorrectionStyle(s)}
              title={s.replace('_', ' ')}
              className={cn(
                'w-8 h-8 rounded-full border-2 transition-colors',
                correctionStyle === s ? 'border-gray-900 scale-110' : 'border-transparent'
              )}
            >
              <div
                className="w-full h-full rounded-full"
                style={{ backgroundColor: STYLE_COLORS[s], opacity: s === 'pencil' ? 0.5 : 0.8 }}
              />
            </button>
          ))}
        </aside>

        {/* Center: Paper canvas */}
        <div className="flex-1 overflow-auto p-4">
          <div
            ref={canvasContainerRef}
            className="relative mx-auto cursor-crosshair"
            style={{
              width: imageSize.width ? `${imageSize.width * zoom}px` : '100%',
              maxWidth: '100%',
            }}
            onClick={handleCanvasClick}
          >
            {imageUrl && (
              <img
                src={imageUrl}
                alt="Student paper"
                onLoad={handleImageLoad}
                className="w-full select-none"
                draggable={false}
                style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
              />
            )}

            {/* Render annotations */}
            {imageLoaded && annotations.map((ann) => {
              const left = `${ann.position.x * 100}%`;
              const top = `${ann.position.y * 100}%`;
              const color = STYLE_COLORS[ann.style || correctionStyle];
              const isSelected = selectedAnnotation === ann.id;

              return (
                <div
                  key={ann.id}
                  className={cn(
                    'absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer',
                    isSelected && 'ring-2 ring-brand-400 ring-offset-1 rounded'
                  )}
                  style={{ left, top }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedAnnotation(ann.id);
                  }}
                >
                  {ann.type === 'checkmark' && (
                    <span className="font-handwriting text-2xl font-bold" style={{ color }}>✓</span>
                  )}
                  {ann.type === 'xmark' && (
                    <span className="font-handwriting text-2xl font-bold" style={{ color }}>✗</span>
                  )}
                  {ann.type === 'circle' && (
                    <div
                      className="w-8 h-8 rounded-full border-2"
                      style={{ borderColor: color }}
                    />
                  )}
                  {ann.type === 'underline' && (
                    <div
                      className="h-0.5"
                      style={{
                        backgroundColor: color,
                        width: `${(ann.bounds?.width ?? 0.1) * (imageSize.width * zoom)}px`,
                      }}
                    />
                  )}
                  {ann.type === 'text_note' && (
                    <span
                      className="font-handwriting text-sm whitespace-nowrap"
                      style={{ color }}
                    >
                      {ann.text}
                    </span>
                  )}
                  {ann.type === 'score_box' && (
                    <span
                      className="font-handwriting text-xl font-bold px-2 py-0.5 border-2 rounded"
                      style={{ color, borderColor: color }}
                    >
                      {ann.text}
                    </span>
                  )}

                  {/* Confidence indicator for AI annotations */}
                  {ann.ai_generated && ann.confidence < 0.7 && (
                    <div className="absolute -top-2 -right-2 w-3 h-3 bg-amber-400 rounded-full" title="Low confidence" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: AI Results panel */}
        <aside className="w-80 bg-white border-l overflow-y-auto shrink-0">
          <div className="p-4 border-b">
            <h2 className="text-sm font-semibold text-gray-900">AI Grading Results</h2>
            {paper.evaluation_result && (
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-bold text-gray-900">
                  {paper.evaluation_result.total_score}
                </span>
                <span className="text-lg text-gray-400">
                  / {paper.evaluation_result.max_score}
                </span>
                {paper.percentage != null && (
                  <span className="ml-auto text-sm font-medium text-gray-500">
                    {paper.percentage}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Questions list */}
          <div className="divide-y">
            {questions.map((q) => (
              <div key={q.number} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-500">Q{q.number}</span>
                  <div className="flex items-center gap-1">
                    {q.is_correct === true && <Check className="w-4 h-4 text-green-500" />}
                    {q.is_correct === false && <X className="w-4 h-4 text-red-500" />}
                    {q.is_correct === null && <AlertTriangle className="w-4 h-4 text-amber-400" />}
                    <span className="text-xs text-gray-500">
                      {q.score}/{q.max_score}
                    </span>
                  </div>
                </div>
                {q.question_text && (
                  <p className="text-xs text-gray-500 mb-1">{q.question_text}</p>
                )}
                <p className="text-sm text-gray-900">
                  Student: <span className="font-medium">{q.student_answer || '—'}</span>
                </p>
                {q.is_correct === false && q.correct_answer && (
                  <p className="text-xs text-green-700 mt-1">
                    Correct: {q.correct_answer}
                  </p>
                )}
                {q.correction_note && (
                  <p className="text-xs text-gray-500 mt-1 italic">{q.correction_note}</p>
                )}
                {q.confidence < 0.7 && (
                  <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Low confidence — please verify
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Overall feedback */}
          {paper.evaluation_result?.overall_feedback && (
            <div className="p-4 border-t">
              <p className="text-xs font-medium text-gray-500 mb-1">AI Feedback</p>
              <p className="text-sm text-gray-700">{paper.evaluation_result.overall_feedback}</p>
            </div>
          )}

          {/* Selected annotation actions */}
          {selectedAnnotation && (
            <div className="p-4 border-t bg-gray-50">
              <p className="text-xs font-medium text-gray-500 mb-2">Selected Annotation</p>
              <button
                onClick={() => removeAnnotation(selectedAnnotation)}
                className="flex items-center gap-1.5 text-sm text-red-600 hover:text-red-700"
              >
                <X className="w-3.5 h-3.5" />
                Delete
              </button>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
