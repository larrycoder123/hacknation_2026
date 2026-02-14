"use client";

/**
 * CloseConversationModal — three-phase dialog for closing a conversation.
 *
 * Phase 1 (form):    Agent picks resolution type + optional notes.
 * Phase 2 (loading): Spinner while the backend generates a ticket and runs
 *                    the learning pipeline (can be dismissed).
 * Phase 3 (result):  Shows ticket number + learning classification
 *                    (SAME_KNOWLEDGE / NEW_KNOWLEDGE / CONTRADICTS).
 */

import { useState } from 'react';
import { CloseConversationPayload, CloseConversationResponse, SelfLearningResult, SuggestedAction, ActionType } from '@/types';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { CheckCircle2, AlertCircle, Loader2, BookOpen, ShieldCheck, Sparkles, X, ArrowUp, ArrowDown, FileText, Link2, Terminal, MessageSquare, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

type ModalPhase = 'form' | 'closing' | 'learning' | 'result';

const SuggestionTypeIcon = ({ type }: { type: ActionType }) => {
    switch (type) {
        case 'script':
            return <Terminal className="w-3.5 h-3.5 text-blue-400" />;
        case 'response':
            return <MessageSquare className="w-3.5 h-3.5 text-primary" />;
        default:
            return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
    }
};

interface CloseConversationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (payload: CloseConversationPayload) => Promise<CloseConversationResponse | null>;
    onLearn: (ticketNumber: string) => Promise<SelfLearningResult | null>;
    conversationId: string;
    sessionSuggestions: SuggestedAction[];
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

export default function CloseConversationModal({ isOpen, onClose, onConfirm, onLearn, conversationId, sessionSuggestions }: CloseConversationModalProps) {
    const [resolutionType, setResolutionType] = useState<CloseConversationPayload['resolution_type']>('Resolved Successfully');
    const [notes, setNotes] = useState('');
    const [phase, setPhase] = useState<ModalPhase>('form');
    const [response, setResponse] = useState<CloseConversationResponse | null>(null);
    const [learningResult, setLearningResult] = useState<SelfLearningResult | null>(null);
    const [learningFailed, setLearningFailed] = useState(false);
    const [appliedIds, setAppliedIds] = useState<Set<string>>(new Set());

    const toggleAppliedId = (id: string) => {
        setAppliedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    if (!isOpen) return null;

    const handleSubmit = async () => {
        setPhase('closing');

        const payload: CloseConversationPayload = {
            conversation_id: conversationId,
            resolution_type: resolutionType,
            notes,
            create_ticket: true,
        };

        // Include applied source IDs only for resolved conversations with suggestions
        if (resolutionType === 'Resolved Successfully' && sessionSuggestions.length > 0) {
            payload.applied_source_ids = Array.from(appliedIds);
        }

        const closeResult = await onConfirm(payload);
        setResponse(closeResult);

        // If resolved with a ticket, run the learning pipeline as a separate request
        const ticketNumber = closeResult?.ticket?.ticket_number;
        if (ticketNumber && resolutionType === 'Resolved Successfully') {
            setPhase('learning');
            const lr = await onLearn(ticketNumber);
            if (lr) {
                setLearningResult(lr);
            } else {
                setLearningFailed(true);
            }
        }

        setPhase('result');
    };

    const handleDone = () => {
        // Reset state for next use
        setPhase('form');
        setResponse(null);
        setLearningResult(null);
        setLearningFailed(false);
        setResolutionType('Resolved Successfully');
        setNotes('');
        setAppliedIds(new Set());
        onClose();
    };

    // ── Loading phases ────────────────────────────────────────────
    if (phase === 'closing' || phase === 'learning') {
        const isLearning = phase === 'learning';
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                <div className="w-full max-w-md bg-card rounded-lg shadow-lg border border-border animate-in fade-in zoom-in-95 duration-200">
                    <div className="p-8 flex flex-col items-center justify-center space-y-5">
                        <div className="relative">
                            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                                <Loader2 className="h-6 w-6 text-primary animate-spin" />
                            </div>
                        </div>
                        <div className="text-center space-y-1">
                            <h3 className="text-base font-semibold text-foreground">
                                {isLearning ? 'Running learning pipeline...' : 'Generating ticket...'}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                                {isLearning
                                    ? 'Analyzing knowledge and updating confidence scores'
                                    : 'Creating ticket from conversation'}
                            </p>
                        </div>
                        {/* Step indicators */}
                        {resolutionType === 'Resolved Successfully' && (
                            <div className="flex items-center gap-3 text-xs">
                                <div className={cn(
                                    "flex items-center gap-1.5",
                                    isLearning ? "text-emerald-500" : "text-primary"
                                )}>
                                    {isLearning
                                        ? <CheckCircle2 className="h-3.5 w-3.5" />
                                        : <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    }
                                    <span className="font-medium">Ticket</span>
                                </div>
                                <div className="w-6 h-px bg-border" />
                                <div className={cn(
                                    "flex items-center gap-1.5",
                                    isLearning ? "text-primary" : "text-muted-foreground/40"
                                )}>
                                    {isLearning
                                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        : <BookOpen className="h-3.5 w-3.5" />
                                    }
                                    <span className="font-medium">Learning</span>
                                </div>
                            </div>
                        )}
                        <button
                            onClick={handleDone}
                            className="text-xs text-amber-500 hover:text-amber-400 font-medium transition-colors mt-2"
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
        const lr = learningResult;
        const classification = lr?.gap_classification;
        const ticketNumber = response?.ticket?.ticket_number;
        const isResolved = resolutionType === 'Resolved Successfully';
        const classInfo = classification ? CLASSIFICATION_DISPLAY[classification] : null;
        const ClassIcon = classInfo?.icon || CheckCircle2;
        const confidenceUpdates = lr?.confidence_updates ?? [];

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
                                <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Ticket</span>
                                <span className="text-sm font-mono font-medium text-foreground">{ticketNumber}</span>
                            </div>
                        )}

                        {/* Learning pipeline details */}
                        {lr && (
                            <div className="space-y-3 p-3.5 bg-muted/20 border border-border/50 rounded-lg">
                                <div className="flex items-center gap-2">
                                    <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Learning Pipeline</span>
                                </div>

                                <p className="text-xs text-muted-foreground">
                                    {lr.retrieval_logs_processed} retrieval log{lr.retrieval_logs_processed !== 1 ? 's' : ''} processed
                                </p>

                                {/* Confidence updates */}
                                {confidenceUpdates.length > 0 && (
                                    <div className="space-y-1.5">
                                        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Confidence Updates</span>
                                        {confidenceUpdates.map((update, idx) => {
                                            const isPositive = update.delta >= 0;
                                            return (
                                                <div key={`${update.source_id}-${idx}`} className="flex items-center justify-between text-xs">
                                                    <div className="flex items-center gap-1.5">
                                                        {isPositive
                                                            ? <ArrowUp className="h-3 w-3 text-emerald-500" />
                                                            : <ArrowDown className="h-3 w-3 text-red-400" />
                                                        }
                                                        <span className="font-mono text-foreground/80">{update.source_id}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className={cn(
                                                            "font-mono font-medium",
                                                            isPositive ? "text-emerald-500" : "text-red-400"
                                                        )}>
                                                            {isPositive ? '+' : ''}{Math.round(update.delta * 100)}%
                                                        </span>
                                                        <span className="text-muted-foreground">
                                                            → {(update.new_confidence * 100).toFixed(0)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}

                                {/* Classification */}
                                {classInfo && (
                                    <div className={cn(
                                        "flex items-start gap-2.5 p-2.5 rounded-md border mt-1",
                                        classification === 'NEW_KNOWLEDGE' && "bg-blue-500/5 border-blue-500/20",
                                        classification === 'SAME_KNOWLEDGE' && "bg-emerald-500/5 border-emerald-500/20",
                                        classification === 'CONTRADICTS' && "bg-amber-500/5 border-amber-500/20",
                                    )}>
                                        <ClassIcon className={cn("h-4 w-4 mt-0.5 flex-shrink-0", classInfo.color)} />
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-foreground/90">
                                                {classInfo.label}
                                            </p>
                                            {/* Matched article for SAME_KNOWLEDGE */}
                                            {classification === 'SAME_KNOWLEDGE' && lr.matched_kb_article_id && (
                                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                    <Link2 className="h-3 w-3" />
                                                    <span>Matched: <span className="font-mono font-medium text-foreground/70">{lr.matched_kb_article_id}</span></span>
                                                    {lr.match_similarity != null && (
                                                        <span className="text-emerald-500 font-mono">({Math.round(lr.match_similarity * 100)}% similarity)</span>
                                                    )}
                                                </div>
                                            )}
                                            {/* Flagged + drafted for CONTRADICTS */}
                                            {classification === 'CONTRADICTS' && (
                                                <div className="space-y-0.5 text-xs text-muted-foreground">
                                                    {lr.matched_kb_article_id && (
                                                        <div className="flex items-center gap-1.5">
                                                            <AlertCircle className="h-3 w-3 text-amber-500" />
                                                            <span>Flagged: <span className="font-mono font-medium text-foreground/70">{lr.matched_kb_article_id}</span></span>
                                                        </div>
                                                    )}
                                                    {lr.drafted_kb_article_id && (
                                                        <div className="flex items-center gap-1.5">
                                                            <Sparkles className="h-3 w-3 text-blue-500" />
                                                            <span>Draft replacement: <span className="font-mono font-medium text-foreground/70">{lr.drafted_kb_article_id}</span></span>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                            {/* Drafted for NEW_KNOWLEDGE */}
                                            {classification === 'NEW_KNOWLEDGE' && lr.drafted_kb_article_id && (
                                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                    <Sparkles className="h-3 w-3 text-blue-500" />
                                                    <span>Draft: <span className="font-mono font-medium text-foreground/70">{lr.drafted_kb_article_id}</span></span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Learning failed */}
                        {isResolved && learningFailed && !lr && (
                            <div className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                                <AlertCircle className="h-4 w-4 mt-0.5 text-amber-500 flex-shrink-0" />
                                <p className="text-sm text-amber-600 dark:text-amber-400 leading-relaxed">
                                    Learning pipeline could not complete. The ticket was saved — learning can be retried later.
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

                        {/* Applied suggestions checklist */}
                        {resolutionType === 'Resolved Successfully' && sessionSuggestions.length > 0 && (
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-foreground uppercase tracking-wider">
                                    Applied Suggestions
                                    <span className="text-muted-foreground font-normal normal-case opacity-50 ml-1">
                                        (Which suggestions helped?)
                                    </span>
                                </label>
                                <div className="max-h-48 overflow-y-auto space-y-1.5 rounded-lg border border-border p-2">
                                    {sessionSuggestions.map((suggestion) => {
                                        const isChecked = appliedIds.has(suggestion.id);
                                        return (
                                            <label
                                                key={suggestion.id}
                                                className={cn(
                                                    "flex items-center gap-3 cursor-pointer p-2.5 border rounded-lg transition-all",
                                                    isChecked
                                                        ? "bg-emerald-500/5 border-emerald-500/20 ring-1 ring-emerald-500/20"
                                                        : "bg-background border-border hover:bg-muted/50"
                                                )}
                                            >
                                                <div className={cn(
                                                    "h-4 w-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors",
                                                    isChecked
                                                        ? "border-emerald-500 bg-emerald-500"
                                                        : "border-muted-foreground"
                                                )}>
                                                    {isChecked && <Check className="h-3 w-3 text-white" />}
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={isChecked}
                                                    onChange={() => toggleAppliedId(suggestion.id)}
                                                    className="sr-only"
                                                />
                                                <SuggestionTypeIcon type={suggestion.type} />
                                                <div className="flex-1 min-w-0">
                                                    <p className={cn(
                                                        "text-sm font-medium truncate",
                                                        isChecked ? "text-emerald-700 dark:text-emerald-400" : "text-foreground"
                                                    )}>
                                                        {suggestion.title}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground truncate">
                                                        {suggestion.source}
                                                    </p>
                                                </div>
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

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
