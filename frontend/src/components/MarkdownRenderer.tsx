"use client";

import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';

interface MarkdownRendererProps {
    content: string;
    className?: string;
}

/**
 * MarkdownRenderer Component
 * 
 * Renders markdown content with proper styling for:
 * - Headings
 * - Lists (ordered and unordered)
 * - Code blocks and inline code
 * - Links
 * - Bold and italic text
 * - Blockquotes
 */
export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
    // Fix markdown list formatting:
    // 1. Merge "1.\n**Text**" → "1. **Text**" (number on its own line)
    // 2. Ensure blank lines before list starts so markdown parses them correctly
    const normalized = content
        .replace(/(\d+)\.\s*\n+\s*(\*\*)/g, '$1. $2')
        .replace(/([^\n])\n(\d+\.\s)/g, '$1\n\n$2')
        .replace(/([^\n])\n([-*]\s)/g, '$1\n\n$2');

    return (
        <div className={cn("prose prose-sm prose-invert max-w-none", className)}>
            <ReactMarkdown
                components={{
                    // Headings
                    h1: ({ children }) => (
                        <h1 className="text-lg font-bold mt-4 mb-2 text-foreground">{children}</h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className="text-base font-semibold mt-3 mb-2 text-foreground">{children}</h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className="text-sm font-semibold mt-2 mb-1 text-foreground">{children}</h3>
                    ),
                    // Paragraphs
                    p: ({ children }) => (
                        <p className="text-sm text-foreground/90 leading-relaxed mb-2">{children}</p>
                    ),
                    // Lists
                    ul: ({ children }) => (
                        <ul className="list-disc list-inside text-sm space-y-1 mb-2 text-foreground/90">{children}</ul>
                    ),
                    ol: ({ children }) => (
                        <ol className="list-decimal list-inside text-sm space-y-1 mb-2 text-foreground/90">{children}</ol>
                    ),
                    li: ({ children }) => (
                        <li className="text-sm text-foreground/90">{children}</li>
                    ),
                    // Code
                    code: ({ className, children, ...props }) => {
                        const isInline = !className;
                        if (isInline) {
                            return (
                                <code className="bg-muted/50 text-primary px-1 py-0.5 rounded text-xs font-mono" {...props}>
                                    {children}
                                </code>
                            );
                        }
                        return (
                            <code className="block bg-muted/30 p-2 rounded-md text-xs font-mono overflow-x-auto border border-border/50" {...props}>
                                {children}
                            </code>
                        );
                    },
                    pre: ({ children }) => (
                        <pre className="bg-muted/30 p-3 rounded-md text-xs font-mono overflow-x-auto mb-2 border border-border/50">
                            {children}
                        </pre>
                    ),
                    // Links
                    a: ({ children, href }) => (
                        <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                            {children}
                        </a>
                    ),
                    // Blockquotes
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-primary/50 pl-3 text-sm text-foreground/70 italic my-2">
                            {children}
                        </blockquote>
                    ),
                    // Strong and emphasis
                    strong: ({ children }) => (
                        <strong className="font-semibold text-foreground">{children}</strong>
                    ),
                    em: ({ children }) => (
                        <em className="italic text-foreground/90">{children}</em>
                    ),
                    // Horizontal rule
                    hr: () => <hr className="border-border/50 my-3" />,
                }}
            >
                {normalized}
            </ReactMarkdown>
        </div>
    );
}
