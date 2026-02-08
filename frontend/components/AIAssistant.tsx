"use client";

import { SuggestedAction, ActionType } from '../app/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Sparkles, Terminal, MessageSquare, AlertCircle, RefreshCw, Check } from 'lucide-react';

interface AIAssistantProps {
    suggestions: SuggestedAction[];
    isLoading: boolean;
    onGetSuggestions: () => void;
    onApplySuggestion: (suggestion: SuggestedAction) => void;
}

const ConfidenceScore = ({ score }: { score: number }) => {
    let colorClass = 'text-muted-foreground';
    if (score >= 0.8) {
        colorClass = 'text-emerald-600 dark:text-emerald-500';
    } else if (score >= 0.6) {
        colorClass = 'text-amber-600 dark:text-amber-500';
    }

    return (
        <span className={cn("text-[10px] font-mono font-medium", colorClass)}>
            {Math.round(score * 100)}% Match
        </span>
    );
};

const ActionIcon = ({ type }: { type: ActionType }) => {
    switch (type) {
        case 'script':
            return <Terminal className="w-3.5 h-3.5 text-blue-500" />;
        case 'response':
            return <MessageSquare className="w-3.5 h-3.5 text-primary" />;
        default:
            return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
    }
}

export default function AIAssistant({ suggestions, isLoading, onGetSuggestions, onApplySuggestion }: AIAssistantProps) {
    return (
        <div className="w-[360px] 2xl:w-[420px] h-full flex flex-col bg-background/50 backdrop-blur-xl flex-shrink-0 border border-border rounded-xl shadow-sm overflow-hidden">
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
                        <div className="h-10 w-10 rounded-lg bg-muted/50 flex items-center justify-center">
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
                                    <div key={i} className="h-32 bg-muted/20 rounded-lg animate-pulse border border-border/40"></div>
                                ))}
                            </div>
                        ) : (
                            <>
                                <div className="flex justify-between items-center px-1 pb-1">
                                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Top Suggestions</span>
                                </div>
                                {suggestions.map((suggestion) => (
                                    <div
                                        key={suggestion.id}
                                        className="group p-3 border border-border rounded-lg bg-card hover:border-border/80 transition-all shadow-sm space-y-2.5"
                                    >
                                        <div className="flex justify-between items-start">
                                            <div className="flex items-center gap-2">
                                                <div className="p-1 rounded-md bg-muted/50 border border-border/50">
                                                    <ActionIcon type={suggestion.type} />
                                                </div>
                                                <span className="text-xs font-medium text-muted-foreground capitalize">{suggestion.type}</span>
                                            </div>
                                            <ConfidenceScore score={suggestion.confidence_score} />
                                        </div>

                                        <div className="space-y-1">
                                            <h3 className="text-sm font-medium text-foreground leading-tight">{suggestion.title}</h3>
                                            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                                                {suggestion.description}
                                            </p>
                                        </div>

                                        {suggestion.type === 'script' && (
                                            <div className="bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                <code className="text-xs text-foreground/80 font-mono whitespace-pre block overflow-x-auto">
                                                    {suggestion.content}
                                                </code>
                                            </div>
                                        )}

                                        {suggestion.type === 'response' && (
                                            <div className="bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                <p className="text-xs text-foreground/80 font-mono whitespace-pre-wrap leading-relaxed">
                                                    {suggestion.content}
                                                </p>
                                            </div>
                                        )}

                                        <div className="flex items-center justify-between pt-2 border-t border-border/40">
                                            <span className="text-[10px] text-muted-foreground truncate max-w-[100px] opacity-70">
                                                {suggestion.source}
                                            </span>

                                            {suggestion.type === 'script' && (
                                                <Button
                                                    onClick={() => onApplySuggestion(suggestion)}
                                                    size="sm"
                                                    className="h-6 text-[10px] bg-foreground text-background hover:bg-foreground/90 gap-1.5 px-2.5 shadow-sm"
                                                >
                                                    <Terminal className="w-3 h-3" />
                                                    Run
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
