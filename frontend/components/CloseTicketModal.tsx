import { useState } from 'react';
import { CloseTicketPayload } from '../app/types';

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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-md bg-white dark:bg-zinc-900 rounded-xl shadow-2xl overflow-hidden border border-zinc-200 dark:border-zinc-800">
                <div className="p-6">
                    <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Close Ticket</h3>

                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">Resolution Status</label>
                            <div className="space-y-2">
                                <label className="flex items-center gap-2 cursor-pointer p-3 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                                    <input
                                        type="radio"
                                        name="resolution"
                                        value="Resolved Successfully"
                                        checked={resolutionType === 'Resolved Successfully'}
                                        onChange={() => setResolutionType('Resolved Successfully')}
                                        className="w-4 h-4 text-blue-600 border-zinc-300 focus:ring-blue-500"
                                    />
                                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Resolved Successfully</span>
                                </label>
                                <label className="flex items-center gap-2 cursor-pointer p-3 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                                    <input
                                        type="radio"
                                        name="resolution"
                                        value="Not Applicable"
                                        checked={resolutionType === 'Not Applicable'}
                                        onChange={() => setResolutionType('Not Applicable')}
                                        className="w-4 h-4 text-blue-600 border-zinc-300 focus:ring-blue-500"
                                    />
                                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Not Applicable / Spam</span>
                                </label>
                            </div>
                        </div>

                        <div>
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">
                                Notes <span className="text-zinc-400 font-normal">(optional)</span>
                            </label>
                            <textarea
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Brief summary of how it was resolved..."
                                className="w-full min-h-[80px] p-3 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm resize-none"
                            />
                        </div>

                        <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg flex gap-3">
                            <div className="text-blue-600 dark:text-blue-400 shrink-0">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <p className="text-xs text-blue-800 dark:text-blue-200">
                                Successful resolutions will be added to the knowledge base to improve future AI suggestions.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="px-6 py-4 bg-zinc-50 dark:bg-zinc-950 border-t border-zinc-200 dark:border-zinc-800 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors shadow-sm"
                    >
                        Close Ticket
                    </button>
                </div>
            </div>
        </div>
    );
}
