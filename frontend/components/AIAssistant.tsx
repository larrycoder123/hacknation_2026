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
        <span className={cn("text-xs font-mono font-medium", colorClass)}>
            {Math.round(score * 100)}% Match
        </span>
    );
};

const ActionIcon = ({ type }: { type: ActionType }) => {
    switch (type) {
        case 'script':
            return <Terminal className="w-4 h-4 text-blue-500" />;
        case 'response':
            return <MessageSquare className="w-4 h-4 text-primary" />;
        default:
            return <AlertCircle className="w-4 h-4 text-red-500" />;
    }
}

export default function AIAssistant({ suggestions, isLoading, onGetSuggestions, onApplySuggestion }: AIAssistantProps) {
    return (
        <div className="w-[400px] 2xl:w-[480px] border-l border-border h-full flex flex-col bg-background flex-shrink-0">
            <div className="p-4 h-16 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary" />
                    <h2 className="text-base font-semibold text-foreground tracking-tight">AI Assistant</h2>
                </div>

            </div>

            <div className="flex-1 overflow-y-auto p-4 scrollbar-hide">
                {suggestions.length === 0 && !isLoading ? (
                    <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-0 animate-in fade-in slide-in-from-bottom-4 duration-700 fill-mode-forwards" style={{ animationDelay: '100ms', opacity: 1 }}>
                        <div className="h-12 w-12 rounded-xl bg-muted/50 flex items-center justify-center">
                            <Sparkles className="w-6 h-6 text-muted-foreground/50" />
                        </div>
                        <div className="space-y-1 max-w-[240px]">
                            <h3 className="text-base font-medium text-foreground">No suggestions yet</h3>
                            <p className="text-sm text-muted-foreground">
                                Analyze the conversation to get relevant scripts, tickets, and actions.
                            </p>
                        </div>
                        <Button
                            onClick={onGetSuggestions}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
                            size="sm"
                        >
                            Analyze Conversation
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {isLoading ? (
                            <div className="space-y-4">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="h-40 bg-muted/20 rounded-xl animate-pulse"></div>
                                ))}
                            </div>
                        ) : (
                            <>
                                <div className="flex justify-between items-center px-1 pb-2">
                                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Top Suggestions</span>
                                    <Button
                                        onClick={onGetSuggestions}
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 text-xs text-muted-foreground hover:text-foreground gap-1.5"
                                    >
                                        <RefreshCw className="w-3 h-3" />
                                        Refresh
                                    </Button>
                                </div>
                                {suggestions.map((suggestion) => (
                                    <div
                                        key={suggestion.id}
                                        className="group p-4 border border-border rounded-xl bg-card hover:border-border/80 transition-all shadow-sm space-y-3"
                                    >
                                        <div className="flex justify-between items-start">
                                            <div className="flex items-center gap-2">
                                                <div className="p-1.5 rounded-md bg-muted/50 border border-border/50">
                                                    <ActionIcon type={suggestion.type} />
                                                </div>
                                                <span className="text-sm font-medium text-muted-foreground capitalize">{suggestion.type}</span>
                                            </div>
                                            <ConfidenceScore score={suggestion.confidence_score} />
                                        </div>

                                        <div className="space-y-1">
                                            <h3 className="text-base font-medium text-foreground leading-tight">{suggestion.title}</h3>
                                            <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3">
                                                {suggestion.description}
                                            </p>
                                        </div>

                                        {suggestion.type === 'script' && (
                                            <div className="bg-muted/30 rounded-md p-3 border border-border/50">
                                                <code className="text-sm text-foreground/80 font-mono whitespace-pre block overflow-x-auto">
                                                    {suggestion.content}
                                                </code>
                                            </div>
                                        )}

                                        {suggestion.type === 'response' && (
                                            <div className="bg-muted/30 rounded-md p-3 border border-border/50">
                                                <p className="text-sm text-foreground/80 font-mono whitespace-pre-wrap leading-relaxed">
                                                    {suggestion.content}
                                                </p>
                                            </div>
                                        )}

                                        <div className="flex items-center justify-between pt-3 border-t border-border/40">
                                            <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                                                {suggestion.source}
                                            </span>

                                            {suggestion.type === 'script' && (
                                                <Button
                                                    onClick={() => onApplySuggestion(suggestion)}
                                                    size="sm"
                                                    className="h-7 text-sm bg-foreground text-background hover:bg-foreground/90 gap-1.5"
                                                >
                                                    <Terminal className="w-3 h-3" />
                                                    Run Script
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
