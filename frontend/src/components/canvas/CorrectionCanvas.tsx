'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { fabric } from 'fabric';
import type { Annotation, CorrectionStyle, AnnotationType } from '@/types';

const STYLE_CONFIG: Record<CorrectionStyle, { color: string; opacity: number; width: number }> = {
  red_pen: { color: '#CC2222', opacity: 0.85, width: 2.5 },
  blue_pen: { color: '#1A4B8C', opacity: 0.80, width: 2.5 },
  pencil: { color: '#4A4A4A', opacity: 0.55, width: 1.8 },
};

interface CorrectionCanvasProps {
  imageUrl: string;
  annotations: Annotation[];
  correctionStyle: CorrectionStyle;
  activeTool: string;
  zoom: number;
  onAnnotationsChange: (annotations: Annotation[]) => void;
  onAnnotationSelect: (id: string | null) => void;
}

export function CorrectionCanvas({
  imageUrl,
  annotations,
  correctionStyle,
  activeTool,
  zoom,
  onAnnotationsChange,
  onAnnotationSelect,
}: CorrectionCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fabricRef = useRef<fabric.Canvas | null>(null);
  const imageObjRef = useRef<fabric.Image | null>(null);
  const [canvasReady, setCanvasReady] = useState(false);

  // Initialize Fabric.js canvas
  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = new fabric.Canvas(canvasRef.current, {
      selection: activeTool === 'select',
      backgroundColor: '#f3f4f6',
    });

    fabricRef.current = canvas;

    // Load background image
    fabric.Image.fromURL(imageUrl, (img) => {
      if (!img || !img.width || !img.height) return;

      imageObjRef.current = img;

      // Set canvas size to image size
      canvas.setWidth(img.width);
      canvas.setHeight(img.height);

      // Set image as background
      canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas), {
        scaleX: 1,
        scaleY: 1,
        originX: 'left',
        originY: 'top',
      });

      setCanvasReady(true);
    }, { crossOrigin: 'anonymous' });

    // Selection events
    canvas.on('selection:created', (e) => {
      const obj = e.selected?.[0];
      if (obj?.data?.annotationId) {
        onAnnotationSelect(obj.data.annotationId);
      }
    });

    canvas.on('selection:cleared', () => {
      onAnnotationSelect(null);
    });

    // Object modification events
    canvas.on('object:modified', () => {
      syncAnnotationsFromCanvas();
    });

    return () => {
      canvas.dispose();
      fabricRef.current = null;
    };
  }, [imageUrl]);

  // Render annotations onto canvas when they change externally
  useEffect(() => {
    if (!canvasReady || !fabricRef.current) return;
    renderAnnotations();
  }, [canvasReady, annotations, correctionStyle]);

  // Update zoom
  useEffect(() => {
    if (!fabricRef.current) return;
    fabricRef.current.setZoom(zoom);
    if (imageObjRef.current) {
      fabricRef.current.setWidth(imageObjRef.current.width! * zoom);
      fabricRef.current.setHeight(imageObjRef.current.height! * zoom);
    }
  }, [zoom]);

  // Update selection mode based on tool
  useEffect(() => {
    if (!fabricRef.current) return;
    fabricRef.current.selection = activeTool === 'select';
    fabricRef.current.forEachObject((obj) => {
      obj.selectable = activeTool === 'select';
      obj.evented = activeTool === 'select';
    });
    // Change cursor
    if (activeTool === 'select') {
      fabricRef.current.defaultCursor = 'default';
    } else if (activeTool === 'text_note') {
      fabricRef.current.defaultCursor = 'text';
    } else {
      fabricRef.current.defaultCursor = 'crosshair';
    }
  }, [activeTool]);

  // Canvas click — add annotation
  useEffect(() => {
    if (!fabricRef.current) return;

    const handler = (opt: fabric.IEvent<MouseEvent>) => {
      if (activeTool === 'select') return;
      if (!opt.pointer) return;

      const pointer = fabricRef.current!.getPointer(opt.e);
      addAnnotationAtPoint(pointer.x, pointer.y);
    };

    fabricRef.current.on('mouse:down', handler);
    return () => {
      fabricRef.current?.off('mouse:down', handler);
    };
  }, [activeTool, correctionStyle, annotations]);

  // Render all annotations as Fabric objects
  const renderAnnotations = useCallback(() => {
    const canvas = fabricRef.current;
    if (!canvas || !imageObjRef.current) return;

    // Remove existing annotation objects (keep background)
    const objects = canvas.getObjects().filter((o) => o.data?.isAnnotation);
    objects.forEach((o) => canvas.remove(o));

    const imgW = imageObjRef.current.width!;
    const imgH = imageObjRef.current.height!;
    const style = STYLE_CONFIG[correctionStyle];

    annotations.forEach((ann) => {
      const x = ann.position.x * imgW;
      const y = ann.position.y * imgH;
      let obj: fabric.Object | null = null;

      switch (ann.type) {
        case 'checkmark':
          obj = createCheckmark(x, y, style);
          break;
        case 'xmark':
          obj = createXmark(x, y, style);
          break;
        case 'circle':
          obj = createCircle(x, y, ann.bounds, imgW, imgH, style);
          break;
        case 'underline':
          obj = createUnderline(x, y, ann.bounds, imgW, style);
          break;
        case 'text_note':
          obj = createTextNote(x, y, ann.text || '', style);
          break;
        case 'score_box':
          obj = createScoreBox(x, y, ann.text || '', style);
          break;
      }

      if (obj) {
        obj.data = {
          isAnnotation: true,
          annotationId: ann.id,
          annotationType: ann.type,
        };
        obj.selectable = activeTool === 'select';
        obj.evented = activeTool === 'select';

        // Low confidence indicator
        if (ann.ai_generated && ann.confidence < 0.7) {
          obj.set('shadow', new fabric.Shadow({
            color: '#fbbf24',
            blur: 8,
            offsetX: 0,
            offsetY: 0,
          }));
        }

        canvas.add(obj);
      }
    });

    canvas.renderAll();
  }, [annotations, correctionStyle, activeTool]);

  // Create annotation objects
  function createCheckmark(
    x: number, y: number,
    style: { color: string; opacity: number; width: number }
  ): fabric.Object {
    // Natural checkmark with slight wobble
    const wobble = () => (Math.random() - 0.5) * 2;
    const path = new fabric.Path(
      `M ${-8 + wobble()} ${4 + wobble()} L ${-2 + wobble()} ${12 + wobble()} L ${12 + wobble()} ${-6 + wobble()}`,
      {
        left: x,
        top: y,
        fill: '',
        stroke: style.color,
        strokeWidth: style.width,
        strokeLineCap: 'round',
        strokeLineJoin: 'round',
        opacity: style.opacity,
        originX: 'center',
        originY: 'center',
      }
    );
    return path;
  }

  function createXmark(
    x: number, y: number,
    style: { color: string; opacity: number; width: number }
  ): fabric.Object {
    const wobble = () => (Math.random() - 0.5) * 1.5;
    const group = new fabric.Group([
      new fabric.Line(
        [-8 + wobble(), -8 + wobble(), 8 + wobble(), 8 + wobble()],
        { stroke: style.color, strokeWidth: style.width, strokeLineCap: 'round' }
      ),
      new fabric.Line(
        [8 + wobble(), -8 + wobble(), -8 + wobble(), 8 + wobble()],
        { stroke: style.color, strokeWidth: style.width, strokeLineCap: 'round' }
      ),
    ], {
      left: x,
      top: y,
      opacity: style.opacity,
      originX: 'center',
      originY: 'center',
    });
    return group;
  }

  function createCircle(
    x: number, y: number,
    bounds: { width: number; height: number } | undefined,
    imgW: number, imgH: number,
    style: { color: string; opacity: number; width: number }
  ): fabric.Object {
    const rx = ((bounds?.width ?? 0.03) * imgW) / 2;
    const ry = ((bounds?.height ?? 0.02) * imgH) / 2;
    return new fabric.Ellipse({
      left: x,
      top: y,
      rx: Math.max(rx, 15),
      ry: Math.max(ry, 12),
      fill: '',
      stroke: style.color,
      strokeWidth: style.width,
      opacity: style.opacity,
      originX: 'center',
      originY: 'center',
    });
  }

  function createUnderline(
    x: number, y: number,
    bounds: { width: number; height: number } | undefined,
    imgW: number,
    style: { color: string; opacity: number; width: number }
  ): fabric.Object {
    const length = (bounds?.width ?? 0.1) * imgW;
    // Slightly wavy line
    const points: string[] = [`M 0 0`];
    const segments = Math.max(4, Math.floor(length / 20));
    for (let i = 1; i <= segments; i++) {
      const px = (i / segments) * length;
      const py = Math.sin(i * 1.5) * 1.5;
      points.push(`L ${px} ${py}`);
    }
    return new fabric.Path(points.join(' '), {
      left: x,
      top: y,
      fill: '',
      stroke: style.color,
      strokeWidth: style.width,
      strokeLineCap: 'round',
      opacity: style.opacity,
    });
  }

  function createTextNote(
    x: number, y: number, text: string,
    style: { color: string; opacity: number }
  ): fabric.Object {
    return new fabric.IText(text, {
      left: x,
      top: y,
      fontFamily: 'Caveat, cursive',
      fontSize: 20,
      fill: style.color,
      opacity: style.opacity,
      editable: true,
      angle: (Math.random() - 0.5) * 3, // Slight rotation
    });
  }

  function createScoreBox(
    x: number, y: number, text: string,
    style: { color: string; opacity: number; width: number }
  ): fabric.Object {
    const textObj = new fabric.Text(text, {
      fontFamily: 'Caveat, cursive',
      fontSize: 28,
      fill: style.color,
    });

    const padding = 8;
    const rect = new fabric.Rect({
      width: textObj.width! + padding * 2,
      height: textObj.height! + padding * 2,
      fill: '',
      stroke: style.color,
      strokeWidth: style.width + 0.5,
      rx: 4,
      ry: 4,
    });

    // Center text in rect
    textObj.set({
      left: padding,
      top: padding,
    });

    return new fabric.Group([rect, textObj], {
      left: x,
      top: y,
      opacity: style.opacity,
      originX: 'center',
      originY: 'center',
    });
  }

  // Add annotation from click
  const addAnnotationAtPoint = (canvasX: number, canvasY: number) => {
    if (!imageObjRef.current) return;
    const imgW = imageObjRef.current.width!;
    const imgH = imageObjRef.current.height!;

    const xPct = canvasX / imgW;
    const yPct = canvasY / imgH;

    const id = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    const newAnn: Annotation = {
      id,
      type: activeTool as AnnotationType,
      position: { x: xPct, y: yPct },
      style: correctionStyle,
      ai_generated: false,
      confidence: 1.0,
    };

    if (activeTool === 'text_note') {
      const text = prompt('Enter correction note:');
      if (!text) return;
      newAnn.text = text;
    } else if (activeTool === 'score_box') {
      const score = prompt('Enter score (e.g. 8/10):');
      if (!score) return;
      newAnn.text = score;
    } else if (activeTool === 'circle') {
      newAnn.bounds = { width: 0.05, height: 0.03 };
    } else if (activeTool === 'underline') {
      newAnn.bounds = { width: 0.12, height: 0 };
    }

    onAnnotationsChange([...annotations, newAnn]);
  };

  // Sync positions after user drags/resizes objects
  const syncAnnotationsFromCanvas = () => {
    const canvas = fabricRef.current;
    if (!canvas || !imageObjRef.current) return;

    const imgW = imageObjRef.current.width!;
    const imgH = imageObjRef.current.height!;

    const updated = annotations.map((ann) => {
      const obj = canvas.getObjects().find((o) => o.data?.annotationId === ann.id);
      if (!obj) return ann;

      return {
        ...ann,
        position: {
          x: (obj.left ?? 0) / imgW,
          y: (obj.top ?? 0) / imgH,
        },
      };
    });

    onAnnotationsChange(updated);
  };

  return (
    <div className="relative">
      <canvas ref={canvasRef} />
      {!canvasReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <div className="text-sm text-gray-500">Loading paper...</div>
        </div>
      )}
    </div>
  );
}
