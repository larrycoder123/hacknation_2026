"use client";

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronUp } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';

interface ExpandableTextProps {
    content: string;
    maxLength?: number;
    maxLines?: number;
    className?: string;
    isMarkdown?: boolean;
}

/**
 * ExpandableText Component
 * 
 * Shows a truncated preview of long text with a "Show more" button.
 * Supports both plain text and markdown content.
 */
export default function ExpandableText({
    content,
    maxLength = 200,
    maxLines = 3,
    className,
    isMarkdown = false
}: ExpandableTextProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    const shouldTruncate = content.length > maxLength;
    const truncatedContent = shouldTruncate && !isExpanded
        ? content.slice(0, maxLength).trimEnd() + '...'
        : content;

    if (isMarkdown) {
        return (
            <div className={cn("relative", className)}>
                <div className={cn(
                    "overflow-hidden transition-all duration-300",
                    !isExpanded && shouldTruncate && "max-h-24"
                )}>
                    <MarkdownRenderer content={isExpanded ? content : truncatedContent} />
                </div>
                {shouldTruncate && (
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 mt-2 font-medium transition-colors"
                    >
                        {isExpanded ? (
                            <>
                                <ChevronUp className="w-3 h-3" />
                                Show less
                            </>
                        ) : (
                            <>
                                <ChevronDown className="w-3 h-3" />
                                Show more
                            </>
                        )}
                    </button>
                )}
            </div>
        );
    }

    return (
        <div className={cn("relative", className)}>
            <div className={cn(
                "overflow-hidden transition-all duration-300",
                !isExpanded && shouldTruncate && `line-clamp-${maxLines}`
            )}>
                <p className="text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed">
                    {isExpanded ? content : truncatedContent}
                </p>
            </div>
            {shouldTruncate && (
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 mt-2 font-medium transition-colors"
                >
                    {isExpanded ? (
                        <>
                            <ChevronUp className="w-3 h-3" />
                            Show less
                        </>
                    ) : (
                        <>
                            <ChevronDown className="w-3 h-3" />
                            Show more
                        </>
                    )}
                </button>
            )}
        </div>
    );
}
