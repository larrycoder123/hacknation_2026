"use client";

import { SuggestedAction, ScoreBreakdown, ActionType } from '@/types';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Sparkles, Terminal, MessageSquare, AlertCircle, RefreshCw, Star, Info } from 'lucide-react';
import ExpandableText from './ExpandableText';
import MarkdownRenderer from './MarkdownRenderer';

interface AIAssistantProps {
    suggestions: SuggestedAction[];
    isLoading: boolean;
    onGetSuggestions: () => void;
    onApplySuggestion: (suggestion: SuggestedAction) => void;
}

const ConfidenceScore = ({ score, breakdown, tooltipAlign = 'right' }: { score: number; breakdown?: ScoreBreakdown; tooltipAlign?: 'left' | 'right' }) => {
    let colorClass = 'text-muted-foreground';
    if (score >= 0.8) {
        colorClass = 'text-emerald-500';
    } else if (score >= 0.6) {
        colorClass = 'text-amber-500';
    }

    const rows = breakdown ? [
        { label: 'Vector Similarity', value: `${Math.round(breakdown.vector_similarity * 100)}%` },
        { label: 'Rerank Score', value: breakdown.rerank_score != null ? `${Math.round(breakdown.rerank_score * 100)}%` : 'N/A' },
        { label: 'Confidence', value: `${Math.round(breakdown.confidence * 100)}%` },
        { label: 'Usage Count', value: `${breakdown.usage_count}` },
        { label: 'Freshness', value: `${Math.round(breakdown.freshness * 100)}%` },
        { label: 'Learning Score', value: `${Math.round(breakdown.learning_score * 100)}%` },
    ] : [];

    return (
        <span className="inline-flex items-center gap-1">
            <span className={cn("text-[10px] font-mono font-medium", colorClass)}>
                {Math.round(score * 100)}% Match
            </span>
            {breakdown && (
                <div className="relative group/tip inline-block">
                    <Info className="w-3 h-3 text-muted-foreground/50 cursor-help" />
                    <div className={cn("absolute top-5 z-50 w-52 opacity-0 scale-95 pointer-events-none group-hover/tip:opacity-100 group-hover/tip:scale-100 group-hover/tip:pointer-events-auto transition-all duration-150 ease-out", tooltipAlign === 'left' ? 'left-0' : 'right-0')}>
                        <div className="bg-popover border border-border rounded-lg shadow-lg p-3 space-y-1.5">
                            <p className="text-[10px] font-semibold text-foreground uppercase tracking-wider mb-2">Score Breakdown</p>
                            {rows.map((row) => (
                                <div key={row.label} className="flex items-center justify-between">
                                    <span className="text-[10px] text-muted-foreground">{row.label}</span>
                                    <span className="text-[10px] font-mono font-medium text-foreground">{row.value}</span>
                                </div>
                            ))}
                            <div className="border-t border-border/50 pt-1.5 mt-1.5 flex items-center justify-between">
                                <span className="text-[10px] font-semibold text-foreground">Final Score</span>
                                <span className={cn("text-[10px] font-mono font-semibold", colorClass)}>
                                    {Math.round(breakdown.final_score * 100)}%
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </span>
    );
};

const ActionIcon = ({ type }: { type: ActionType }) => {
    switch (type) {
        case 'script':
            return <Terminal className="w-3.5 h-3.5 text-blue-400" />;
        case 'response':
            return <MessageSquare className="w-3.5 h-3.5 text-primary" />;
        default:
            return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
    }
}

/**
 * AIAssistant Component
 * 
 * Displays AI-generated suggestions for the current conversation.
 * It shows a list of suggested actions (scripts, responses) with confidence scores.
 */
export default function AIAssistant({ suggestions, isLoading, onGetSuggestions, onApplySuggestion }: AIAssistantProps) {
    return (
        <div className="w-[420px] 2xl:w-[500px] h-full flex flex-col bg-background/50 backdrop-blur-xl flex-shrink-0 border border-border rounded-lg shadow-sm overflow-hidden">
            <div className="p-4 h-14 border-b border-border/50 flex items-center justify-between bg-background/50">
                <div className="flex items-center gap-2">
                    <div className="p-1 rounded-md bg-primary/10">
                        <Sparkles className="w-3.5 h-3.5 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground tracking-tight">AI Assistant</h2>
                </div>
                {suggestions.length > 0 && !isLoading && (
                    <Button
                        onClick={onGetSuggestions}
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground rounded-md"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </Button>
                )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 scrollbar-hide">
                {suggestions.length === 0 && !isLoading ? (
                    <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-0 animate-in fade-in slide-in-from-bottom-4 duration-700 fill-mode-forwards" style={{ animationDelay: '100ms', opacity: 1 }}>
                        <div className="h-10 w-10 rounded-md bg-muted/50 flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-muted-foreground/40" />
                        </div>
                        <div className="space-y-1 max-w-[200px]">
                            <h3 className="text-sm font-medium text-foreground">No suggestions yet</h3>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                Analyze conversations to get context-aware actions.
                            </p>
                        </div>
                        <Button
                            onClick={onGetSuggestions}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm text-xs h-8 px-4"
                            size="sm"
                        >
                            Analyze Context
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {isLoading ? (
                            <div className="space-y-3">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="h-32 bg-muted/20 rounded-md animate-pulse border border-border/40"></div>
                                ))}
                            </div>
                        ) : (
                            <>
                                {/* ── Top Suggestion (adapted) ── */}
                                {suggestions.length > 0 && (() => {
                                    const top = suggestions[0];
                                    const rest = suggestions.slice(1);
                                    return (
                                        <>
                                            <div className="flex items-center gap-1.5 px-1 pb-1">
                                                <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
                                                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Best Match</span>
                                                <ConfidenceScore score={top.confidence_score} breakdown={top.score_breakdown} tooltipAlign="left" />
                                            </div>

                                            <div className="p-3.5 border border-primary/30 rounded-lg bg-primary/5 space-y-3">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <div className="p-1 rounded-md bg-primary/10 border border-primary/20">
                                                            <ActionIcon type={top.type} />
                                                        </div>
                                                        <h3 className="text-sm font-semibold text-foreground leading-tight">{top.title}</h3>
                                                    </div>
                                                </div>

                                                {/* Adapted summary */}
                                                {top.adapted_summary && (
                                                    <div className="text-sm text-foreground/90 leading-relaxed">
                                                        <MarkdownRenderer content={top.adapted_summary} />
                                                    </div>
                                                )}

                                                {/* Source reference */}
                                                <div className="flex items-center justify-between pt-2 border-t border-primary/10">
                                                    <span className="text-[10px] text-muted-foreground font-medium">
                                                        {top.source}
                                                    </span>
                                                    {top.type === 'script' && (
                                                        <Button
                                                            onClick={() => onApplySuggestion(top)}
                                                            size="sm"
                                                            className="h-6 text-[10px] bg-foreground text-background hover:bg-foreground/90 gap-1.5 px-2.5 shadow-sm"
                                                        >
                                                            <Terminal className="w-3 h-3" />
                                                            Run Script
                                                        </Button>
                                                    )}
                                                </div>

                                                {/* Expandable full content */}
                                                <details className="group">
                                                    <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors select-none">
                                                        View full source content
                                                    </summary>
                                                    <div className="mt-2 bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                        <ExpandableText
                                                            content={top.content}
                                                            maxLength={300}
                                                            isMarkdown={top.type !== 'script'}
                                                            className={top.type === 'script' ? "font-mono text-xs" : ""}
                                                        />
                                                    </div>
                                                </details>
                                            </div>

                                            {/* ── Other Suggestions ── */}
                                            {rest.length > 0 && (
                                                <>
                                                    <div className="flex items-center px-1 pt-3 pb-1">
                                                        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Other Suggestions</span>
                                                    </div>
                                                    {rest.map((suggestion) => (
                                                        <div
                                                            key={suggestion.id}
                                                            className="group p-3.5 border border-border rounded-lg bg-card hover:border-border/80 transition-all shadow-sm space-y-3"
                                                        >
                                                            <div className="flex items-center justify-between">
                                                                <div className="flex items-center gap-2">
                                                                    <div className="p-1 rounded-md bg-muted/50 border border-border/50">
                                                                        <ActionIcon type={suggestion.type} />
                                                                    </div>
                                                                    <h3 className="text-sm font-semibold text-foreground leading-tight">{suggestion.title}</h3>
                                                                </div>
                                                                <ConfidenceScore score={suggestion.confidence_score} breakdown={suggestion.score_breakdown} />
                                                            </div>

                                                            {/* Adapted summary */}
                                                            {suggestion.adapted_summary ? (
                                                                <div className="text-sm text-foreground/90 leading-relaxed">
                                                                    <MarkdownRenderer content={suggestion.adapted_summary} />
                                                                </div>
                                                            ) : (
                                                                <ExpandableText
                                                                    content={suggestion.description}
                                                                    maxLength={200}
                                                                    maxLines={3}
                                                                    className="text-xs text-muted-foreground leading-relaxed"
                                                                />
                                                            )}

                                                            {/* Source reference */}
                                                            <div className="flex items-center justify-between pt-2 border-t border-border/40">
                                                                <span className="text-[10px] text-muted-foreground font-medium">
                                                                    {suggestion.source}
                                                                </span>
                                                                {suggestion.type === 'script' && (
                                                                    <Button
                                                                        onClick={() => onApplySuggestion(suggestion)}
                                                                        size="sm"
                                                                        className="h-6 text-[10px] bg-foreground text-background hover:bg-foreground/90 gap-1.5 px-2.5 shadow-sm"
                                                                    >
                                                                        <Terminal className="w-3 h-3" />
                                                                        Run Script
                                                                    </Button>
                                                                )}
                                                            </div>

                                                            {/* Expandable full content */}
                                                            <details className="group">
                                                                <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors select-none">
                                                                    View full source content
                                                                </summary>
                                                                <div className="mt-2 bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                                    <ExpandableText
                                                                        content={suggestion.content}
                                                                        maxLength={300}
                                                                        isMarkdown={suggestion.type !== 'script'}
                                                                        className={suggestion.type === 'script' ? "font-mono text-xs" : ""}
                                                                    />
                                                                </div>
                                                            </details>
                                                        </div>
                                                    ))}
                                                </>
                                            )}
                                        </>
                                    );
                                })()}
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
