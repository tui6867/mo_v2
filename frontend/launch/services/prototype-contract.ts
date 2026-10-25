/** Future integration vocabulary ONLY. No implementation or live endpoint is provided. */
export type SubmissionState = 'not_attempted' | 'submitting' | 'accepted' | 'failed' | 'unknown';
export type DeliveryEvidence = { state: 'delivered' | 'bounced'; providerEventId: string; observedAt: string };
export type ApprovedDraft = { previewId: string; approvalToken: string; expiresAt: string };

export interface FuturePrototypeGateway {
  preview(draft: { recipientId: string; subject: string; body: string }): Promise<{
    previewId: string; sender: string; recipient: string; subject: string; body: string;
  }>;
  approve(previewId: string): Promise<ApprovedDraft>;
  submit(approval: ApprovedDraft): Promise<{ submissionId: string; state: SubmissionState }>;
  status(submissionId: string): Promise<{ state: SubmissionState; delivery?: DeliveryEvidence }>;
}

// This is NOT the current pilot's API contract. Implement only after a separate
// authenticated integration review. Never map simulated "delivered" to acceptance.
