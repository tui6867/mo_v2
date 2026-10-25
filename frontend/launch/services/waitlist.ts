/** Public UI boundary. Replace this implementation, not the form, when collection is approved. */
export type WaitlistApplication = { email: string; goal: string; consent: boolean };
export type WaitlistResult = { mode: 'preview'; stored: false } | { mode: 'live'; stored: true };
export interface WaitlistGateway {
  readonly mode: 'preview' | 'live';
  apply(application: WaitlistApplication): Promise<WaitlistResult>;
}

export const previewWaitlist: WaitlistGateway = {
  mode: 'preview',
  async apply(application) {
    if (!application.consent || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(application.email.trim())) {
      throw new Error('Enter a valid email address and confirm the contact preference.');
    }
    if (application.email.length > 254 || application.goal.length > 300) {
      throw new Error('Please keep your email under 255 characters and your goal under 301.');
    }
    // Deliberately no fetch, analytics, localStorage, Supabase, or prototype call.
    return { mode: 'preview', stored: false };
  },
};
