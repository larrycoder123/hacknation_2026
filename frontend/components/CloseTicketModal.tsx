import { useState } from 'react';
import { CloseTicketPayload } from '../app/types';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CloseTicketModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (payload: CloseTicketPayload) => void;
    ticketId: string;
}

export default function CloseTicketModal({ isOpen, onClose, onConfirm, ticketId }: CloseTicketModalProps) {
    const [resolutionType, setResolutionType] = useState<CloseTicketPayload['resolution_type']>('Resolved Successfully');
    const [notes, setNotes] = useState('');

    if (!isOpen) return null;

    const handleSubmit = () => {
        onConfirm({
            ticket_id: ticketId,
            resolution_type: resolutionType,
            notes,
            add_to_knowledge_base: true,
        });
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm transition-all duration-100 data-[state=closed]:animate-out data-[state=closed]:fade-out data-[state=open]:fade-in">
            <div className="w-full max-w-md bg-card rounded-xl shadow-lg border border-border animate-in fade-in zoom-in-95 duration-200">
                <div className="p-6 space-y-6">
                    <div>
                        <h3 className="text-lg font-semibold text-foreground tracking-tight">Close Ticket</h3>
                        <p className="text-sm text-muted-foreground mt-1">Select a resolution status for ticket #{ticketId}</p>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-3">
                            <label className="text-xs font-medium text-foreground uppercase tracking-wider">Resolution Status</label>
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
                                    <span className={cn("text-sm font-medium", resolutionType === 'Resolved Successfully' ? "text-emerald-700 dark:text-emerald-400" : "text-foreground")}>
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
                                    <span className={cn("text-sm font-medium", resolutionType === 'Not Applicable' ? "text-slate-700 dark:text-slate-400" : "text-foreground")}>
                                        Not Applicable / Spam
                                    </span>
                                </label>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-medium text-foreground uppercase tracking-wider">
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
                            <p className="text-[11px] text-primary/80 leading-relaxed">
                                Successful resolutions will be added to the knowledge base to improve future AI suggestions.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="px-6 py-4 bg-muted/30 border-t border-border flex justify-end gap-3">
                    <Button
                        variant="ghost"
                        onClick={onClose}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        className="bg-primary hover:bg-primary/90 text-primary-foreground min-w-[100px]"
                    >
                        Close Ticket
                    </Button>
                </div>
            </div>
        </div>
    );
}
