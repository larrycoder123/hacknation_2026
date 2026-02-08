"use client";

import { useState } from 'react';
import { CloseConversationPayload, CloseConversationResponse } from '@/types';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { CheckCircle2, AlertCircle, Loader2, BookOpen, ShieldCheck, Sparkles, X } from 'lucide-react';
import { cn } from '@/lib/utils';

type ModalPhase = 'form' | 'loading' | 'result';

interface CloseConversationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (payload: CloseConversationPayload) => Promise<CloseConversationResponse | null>;
    conversationId: string;
}

const CLASSIFICATION_DISPLAY: Record<string, { label: string; icon: typeof BookOpen; color: string }> = {
    SAME_KNOWLEDGE: {
        label: "Knowledge confirmed — existing article boosted",
        icon: ShieldCheck,
        color: "text-emerald-500",
    },
    NEW_KNOWLEDGE: {
        label: "Knowledge gap detected — new KB article drafted for review",
        icon: Sparkles,
        color: "text-blue-500",
    },
    CONTRADICTS: {
        label: "Contradiction detected — existing KB flagged for review",
        icon: AlertCircle,
        color: "text-amber-500",
    },
};

export default function CloseConversationModal({ isOpen, onClose, onConfirm, conversationId }: CloseConversationModalProps) {
    const [resolutionType, setResolutionType] = useState<CloseConversationPayload['resolution_type']>('Resolved Successfully');
    const [notes, setNotes] = useState('');
    const [phase, setPhase] = useState<ModalPhase>('form');
    const [response, setResponse] = useState<CloseConversationResponse | null>(null);

    if (!isOpen) return null;

    const handleSubmit = async () => {
        setPhase('loading');

        const result = await onConfirm({
            conversation_id: conversationId,
            resolution_type: resolutionType,
            notes,
            create_ticket: true,
        });

        setResponse(result);
        setPhase('result');
    };

    const handleDone = () => {
        // Reset state for next use
        setPhase('form');
        setResponse(null);
        setResolutionType('Resolved Successfully');
        setNotes('');
        onClose();
    };

    // ── Loading phase ─────────────────────────────────────────────
    if (phase === 'loading') {
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                <div className="w-full max-w-md bg-card rounded-lg shadow-lg border border-border animate-in fade-in zoom-in-95 duration-200">
                    <div className="p-8 flex flex-col items-center justify-center space-y-4">
                        <div className="relative">
                            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                                <Loader2 className="h-6 w-6 text-primary animate-spin" />
                            </div>
                        </div>
                        <div className="text-center space-y-1">
                            <h3 className="text-base font-semibold text-foreground">
                                {resolutionType === 'Resolved Successfully'
                                    ? 'Running learning pipeline...'
                                    : 'Closing conversation...'}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                                {resolutionType === 'Resolved Successfully'
                                    ? 'Generating ticket and analyzing knowledge'
                                    : 'This will only take a moment'}
                            </p>
                        </div>
                        <button
                            onClick={handleDone}
                            className="text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors mt-2"
                        >
                            Dismiss — processing continues in background
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // ── Result phase ──────────────────────────────────────────────
    if (phase === 'result') {
        const classification = response?.learning_result?.gap_classification;
        const ticketNumber = response?.ticket?.ticket_number;
        const isResolved = resolutionType === 'Resolved Successfully';
        const classInfo = classification ? CLASSIFICATION_DISPLAY[classification] : null;
        const ClassIcon = classInfo?.icon || CheckCircle2;

        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                <div className="w-full max-w-md bg-card rounded-lg shadow-lg border border-border animate-in fade-in zoom-in-95 duration-200">
                    <div className="p-6 space-y-5">
                        {/* Status header */}
                        <div className="flex items-start gap-3">
                            <div className={cn(
                                "h-10 w-10 rounded-full flex items-center justify-center flex-shrink-0",
                                isResolved ? "bg-emerald-500/10" : "bg-slate-500/10"
                            )}>
                                <CheckCircle2 className={cn(
                                    "h-5 w-5",
                                    isResolved ? "text-emerald-500" : "text-slate-500"
                                )} />
                            </div>
                            <div>
                                <h3 className="text-base font-semibold text-foreground">
                                    Conversation closed
                                </h3>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    {isResolved ? 'Resolved successfully' : 'Marked as not applicable'}
                                </p>
                            </div>
                        </div>

                        {/* Ticket info */}
                        {ticketNumber && (
                            <div className="flex items-center gap-2 px-3 py-2 bg-muted/30 border border-border/50 rounded-md">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Ticket</span>
                                <span className="text-sm font-mono font-medium text-foreground">{ticketNumber}</span>
                            </div>
                        )}

                        {/* Learning classification */}
                        {classInfo && (
                            <div className={cn(
                                "flex items-start gap-3 p-3 rounded-lg border",
                                classification === 'NEW_KNOWLEDGE' && "bg-blue-500/5 border-blue-500/20",
                                classification === 'SAME_KNOWLEDGE' && "bg-emerald-500/5 border-emerald-500/20",
                                classification === 'CONTRADICTS' && "bg-amber-500/5 border-amber-500/20",
                            )}>
                                <ClassIcon className={cn("h-4 w-4 mt-0.5 flex-shrink-0", classInfo.color)} />
                                <p className="text-sm text-foreground/80 leading-relaxed">
                                    {classInfo.label}
                                </p>
                            </div>
                        )}

                        {/* Not applicable — no learning */}
                        {!isResolved && (
                            <div className="flex items-start gap-3 p-3 bg-muted/20 border border-border/50 rounded-lg">
                                <X className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    Not added to learning pipeline
                                </p>
                            </div>
                        )}
                    </div>

                    <div className="px-6 py-4 bg-muted/30 border-t border-border flex justify-end">
                        <Button
                            onClick={handleDone}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground min-w-[80px]"
                        >
                            Done
                        </Button>
                    </div>
                </div>
            </div>
        );
    }

    // ── Form phase (default) ──────────────────────────────────────
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm transition-all duration-100">
            <div className="w-full max-w-md bg-card rounded-lg shadow-lg border border-border animate-in fade-in zoom-in-95 duration-200">
                <div className="p-6 space-y-6">
                    <div>
                        <h3 className="text-lg font-semibold text-foreground tracking-tight">Close Conversation</h3>
                        <p className="text-sm text-muted-foreground mt-1">Select a resolution status for this conversation</p>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-3">
                            <label className="text-sm font-medium text-foreground uppercase tracking-wider">Resolution Status</label>
                            <div className="grid grid-cols-1 gap-2">
                                <label className={cn(
                                    "flex items-center gap-3 cursor-pointer p-3 border rounded-lg transition-all",
                                    resolutionType === 'Resolved Successfully'
                                        ? "bg-emerald-500/5 border-emerald-500/20 ring-1 ring-emerald-500/20"
                                        : "bg-background border-border hover:bg-muted/50"
                                )}>
                                    <input
                                        type="radio"
                                        name="resolution"
                                        value="Resolved Successfully"
                                        checked={resolutionType === 'Resolved Successfully'}
                                        onChange={() => setResolutionType('Resolved Successfully')}
                                        className="sr-only"
                                    />
                                    <div className={cn(
                                        "h-4 w-4 rounded-full border flex items-center justify-center",
                                        resolutionType === 'Resolved Successfully' ? "border-emerald-500 bg-emerald-500" : "border-muted-foreground"
                                    )}>
                                        {resolutionType === 'Resolved Successfully' && <CheckCircle2 className="h-3 w-3 text-white" />}
                                    </div>
                                    <span className={cn("text-base font-medium", resolutionType === 'Resolved Successfully' ? "text-emerald-700 dark:text-emerald-400" : "text-foreground")}>
                                        Resolved Successfully
                                    </span>
                                </label>

                                <label className={cn(
                                    "flex items-center gap-3 cursor-pointer p-3 border rounded-lg transition-all",
                                    resolutionType === 'Not Applicable'
                                        ? "bg-slate-500/5 border-slate-500/20 ring-1 ring-slate-500/20"
                                        : "bg-background border-border hover:bg-muted/50"
                                )}>
                                    <input
                                        type="radio"
                                        name="resolution"
                                        value="Not Applicable"
                                        checked={resolutionType === 'Not Applicable'}
                                        onChange={() => setResolutionType('Not Applicable')}
                                        className="sr-only"
                                    />
                                    <div className={cn(
                                        "h-4 w-4 rounded-full border flex items-center justify-center",
                                        resolutionType === 'Not Applicable' ? "border-slate-500 bg-slate-500" : "border-muted-foreground"
                                    )}>
                                        {resolutionType === 'Not Applicable' && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
                                    </div>
                                    <span className={cn("text-base font-medium", resolutionType === 'Not Applicable' ? "text-slate-700 dark:text-slate-400" : "text-foreground")}>
                                        Not Applicable / Spam
                                    </span>
                                </label>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-foreground uppercase tracking-wider">
                                Notes <span className="text-muted-foreground font-normal normal-case opacity-50 ml-1">(Optional)</span>
                            </label>
                            <Textarea
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Brief summary of how it was resolved..."
                                className="min-h-[100px] resize-none"
                            />
                        </div>

                        <div className="flex items-start gap-3 p-3 bg-primary/5 border border-primary/10 rounded-lg">
                            <AlertCircle className="h-4 w-4 text-primary mt-0.5" />
                            <p className="text-sm text-primary/80 leading-relaxed">
                                Successful resolutions will generate a ticket record to improve future AI suggestions.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="px-6 py-4 bg-muted/30 border-t border-border flex justify-end gap-3">
                    <Button
                        variant="ghost"
                        onClick={handleDone}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        className="bg-primary hover:bg-primary/90 text-primary-foreground min-w-[100px]"
                    >
                        Close Conversation
                    </Button>
                </div>
            </div>
        </div>
    );
}
