import { SuggestedAction, ActionType } from '../app/types';

interface AIAssistantProps {
    suggestions: SuggestedAction[];
    isLoading: boolean;
    onGetSuggestions: () => void;
    onApplySuggestion: (suggestion: SuggestedAction) => void;
}

// Simplified badge without background color for less "rainbow" look
const ConfidenceScore = ({ score }: { score: number }) => {
    let colorClass = 'text-zinc-500';
    if (score >= 0.8) {
        colorClass = 'text-green-600 dark:text-green-400';
    } else if (score >= 0.6) {
        colorClass = 'text-yellow-600 dark:text-yellow-400';
    }

    return (
        <span className={`text-xs font-mono font-medium ${colorClass}`}>
            {Math.round(score * 100)}% Match
        </span>
    );
};

const ActionIcon = ({ type }: { type: ActionType }) => {
    switch (type) {
        case 'script':
            return (
                <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
            );
        case 'response':
            return (
                <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
            );
        default:
            return (
                <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            );
    }
}

export default function AIAssistant({ suggestions, isLoading, onGetSuggestions, onApplySuggestion }: AIAssistantProps) {
    return (
        // Increased width to w-96 (24rem / 384px)
        <div className="w-96 border-l border-zinc-200 dark:border-zinc-800 h-full flex flex-col bg-white dark:bg-zinc-950 flex-shrink-0">
            <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">AI Assistant</h2>
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-900 px-2 py-1 rounded-full border border-zinc-200 dark:border-zinc-800">
                    Beta
                </span>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
                {suggestions.length === 0 && !isLoading ? (
                    <div className="text-center py-8">
                        <div className="text-zinc-300 dark:text-zinc-700 mb-4">
                            <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                            </svg>
                        </div>
                        <p className="text-sm text-zinc-500 mb-4">
                            Analyze the ticket to get relevant scripts, knowledge base articles, and actions.
                        </p>
                        <button
                            onClick={onGetSuggestions}
                            className="w-full py-2 px-4 bg-zinc-900 dark:bg-zinc-100 hover:opacity-90 text-white dark:text-black text-sm font-medium rounded-md transition-all shadow-sm"
                        >
                            Analyze & Get Suggestions
                        </button>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {isLoading ? (
                            <div className="space-y-4 animate-pulse">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="h-32 bg-zinc-100 dark:bg-zinc-900 rounded-lg"></div>
                                ))}
                            </div>
                        ) : (
                            <>
                                <div className="flex justify-between items-center px-1">
                                    <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Top Suggestions</span>
                                    <button onClick={onGetSuggestions} className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 font-medium">
                                        Refresh
                                    </button>
                                </div>
                                {suggestions.map((suggestion) => (
                                    <div key={suggestion.id} className="group p-4 border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 hover:border-zinc-300 dark:hover:border-zinc-700 transition-all shadow-sm">
                                        <div className="flex justify-between items-start mb-3">
                                            <div className="flex items-center gap-2">
                                                <ActionIcon type={suggestion.type} />
                                                <span className="text-xs font-medium text-zinc-500 capitalize">{suggestion.type}</span>
                                            </div>
                                            <ConfidenceScore score={suggestion.confidence_score} />
                                        </div>

                                        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-2">{suggestion.title}</h3>
                                        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4 leading-relaxed">
                                            {suggestion.description}
                                        </p>

                                        {suggestion.type === 'script' && (
                                            <div className="bg-zinc-900 rounded-md p-3 mb-4 overflow-x-auto border border-zinc-800">
                                                <code className="text-xs text-zinc-300 font-mono whitespace-pre block">{suggestion.content}</code>
                                            </div>
                                        )}

                                        {suggestion.type === 'response' && (
                                            // Displaying knowledge base article content more prominently, but truncated visually if too long (mocking truncation via simple CSS or just showing it all since user asked to see it)
                                            <div className="bg-zinc-50 dark:bg-zinc-950/50 border border-zinc-200 dark:border-zinc-800 rounded-md p-3 mb-4">
                                                <p className="text-xs text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap font-mono">{suggestion.content}</p>
                                            </div>
                                        )}

                                        <div className="flex items-center justify-between pt-2 border-t border-zinc-100 dark:border-zinc-800/50">
                                            <span className="text-[10px] text-zinc-400">Source: {suggestion.source}</span>

                                            {suggestion.type === 'script' ? (
                                                <button
                                                    onClick={() => onApplySuggestion(suggestion)}
                                                    className="px-3 py-1.5 bg-zinc-900 dark:bg-white text-white dark:text-black text-xs font-medium rounded hover:opacity-90 transition-opacity"
                                                >
                                                    Run Script
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={() => onApplySuggestion(suggestion)}
                                                    className="ml-auto text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 hover:underline flex items-center gap-1"
                                                >
                                                    Use This
                                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                                                    </svg>
                                                </button>
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
