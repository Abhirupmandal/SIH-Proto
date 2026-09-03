'use client';

import React, { useMemo } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Clock,
  Calendar,
  Layers,
} from 'lucide-react';

export interface TimelineSliderProps {
  minDate: string;
  maxDate: string;
  currentDate: string;
  onChange: (dateIso: string) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
}

export const TimelineSlider: React.FC<TimelineSliderProps> = ({
  minDate,
  maxDate,
  currentDate,
  onChange,
  isPlaying,
  onTogglePlay,
}) => {
  const minTime = useMemo(() => new Date(minDate).getTime(), [minDate]);
  const maxTime = useMemo(() => new Date(maxDate).getTime(), [maxDate]);
  const currentTime = useMemo(() => new Date(currentDate).getTime(), [currentDate]);

  // Safe clamping
  const clampedTime = Math.min(Math.max(currentTime, minTime), maxTime);

  // Calculate percentage for progress fill
  const progressPercent = useMemo(() => {
    if (maxTime <= minTime) return 0;
    return Math.min(100, Math.max(0, ((clampedTime - minTime) / (maxTime - minTime)) * 100));
  }, [clampedTime, minTime, maxTime]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    const date = new Date(val);
    onChange(date.toISOString());
  };

  const handleReset = () => {
    onChange(new Date(minTime).toISOString());
  };

  // Format date display (e.g., "12 Aug 2026, 14:30")
  const formatDisplayDate = (dateStr: string) => {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const day = d.getDate();
    const month = d.toLocaleString('en-US', { month: 'short' });
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day} ${month} ${year}, ${hours}:${minutes}`;
  };

  const formatShortDate = (dateStr: string) => {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const day = d.getDate();
    const month = d.toLocaleString('en-US', { month: 'short' });
    return `${day} ${month}`;
  };

  return (
    <div className="w-full max-w-4xl mx-auto bg-slate-900/90 border border-slate-800 rounded-lg px-4 py-2.5 shadow-2xl backdrop-blur-md text-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3 select-none">
      {/* Left: Play/Pause & Reset Controls */}
      <div className="flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          onClick={onTogglePlay}
          aria-label={isPlaying ? 'Pause timeline playback' : 'Start timeline playback'}
          className={`p-2 rounded-lg transition-all duration-200 flex items-center justify-center ${
            isPlaying
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
              : 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 hover:bg-indigo-600/40'
          }`}
          title={isPlaying ? 'Pause Playback (800ms step)' : 'Play Chronological Evolution'}
        >
          {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
        </button>

        <button
          type="button"
          onClick={handleReset}
          aria-label="Reset timeline to start"
          className="p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors border border-transparent hover:border-slate-700"
          title="Rewind to Aug 10 Start"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Center: Range Slider with Progress Fill and Range Markers */}
      <div className="flex-1 w-full flex flex-col gap-1 px-2">
        <div className="relative flex items-center w-full">
          {/* Custom Styled Slider Input */}
          <input
            type="range"
            min={minTime}
            max={maxTime}
            step={3600000} // 1 hour step resolution
            value={clampedTime}
            onChange={handleSliderChange}
            aria-label="Temporal scrubber"
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            style={{
              background: `linear-gradient(to right, #6366f1 0%, #38bdf8 ${progressPercent}%, #1e293b ${progressPercent}%, #1e293b 100%)`,
            }}
          />
        </div>

        {/* Min / Max Date Boundary Labels */}
        <div className="flex justify-between text-[10px] font-mono text-slate-500 px-0.5">
          <span>{formatShortDate(minDate)} (Start)</span>
          <span className="text-slate-400 font-semibold">{progressPercent.toFixed(0)}% Chronology</span>
          <span>{formatShortDate(maxDate)} (End)</span>
        </div>
      </div>

      {/* Right: Current Active Scrub Timestamp Display & Badge */}
      <div className="flex items-center gap-2.5 shrink-0">
        <div className="flex flex-col items-end">
          <div className="flex items-center gap-1.5 text-xs font-mono text-slate-200 font-medium">
            <Clock className="w-3.5 h-3.5 text-sky-400 shrink-0" />
            <span>{formatDisplayDate(currentDate)}</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            {isPlaying ? 'Auto-stepping (800ms)' : 'Scrub Filter Mode'}
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-1 px-2 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-[10px] font-semibold text-indigo-300 uppercase tracking-wider">
          <Layers className="w-3 h-3 text-indigo-400" />
          <span>Temporal Window</span>
        </div>
      </div>
    </div>
  );
};

export default TimelineSlider;
