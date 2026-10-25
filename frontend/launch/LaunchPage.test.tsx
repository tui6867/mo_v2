import { act, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LaunchPage } from './LaunchPage';
import { WorkflowDemo } from './components/WorkflowDemo';
import { WaitlistDialog } from './components/WaitlistDialog';
import { previewWaitlist } from './services/waitlist';

let reduced = false;
beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: reduced, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal('fetch', vi.fn());
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); reduced = false; });

async function reviewedDemo() {
  const user = userEvent.setup();
  render(<WorkflowDemo onApply={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: /Bring your experience in/ }));
  await user.click(screen.getByRole('button', { name: 'Set permissions' }));
  await user.click(screen.getByRole('button', { name: 'Make it personal' }));
  await user.click(screen.getByRole('button', { name: 'Review messages' }));
  expect(screen.getByRole('button', { name: 'Simulate sending' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Sam Rivera' }));
  await user.click(screen.getByRole('button', { name: 'Casey Chen' }));
  await user.click(screen.getByLabelText('I approve these sample messages for a simulated send.'));
  return user;
}

describe('launch template', () => {
  it('renders the approved sections and honest availability without calling the pilot', () => {
    render(<LaunchPage />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('The future ofnetworking.');
    expect(screen.getByRole('heading', { name: 'An ambitious vision. A working foundation.' })).toBeInTheDocument();
    expect(screen.getByText(/Interactive concept · Fictional data/)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('loads only sample files and gates the next step on simulated permissions', async () => {
    const user = userEvent.setup();
    render(<WorkflowDemo onApply={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Set permissions' })).toBeDisabled();
    expect(document.querySelector('input[type="file"]')).toBeNull();
    await user.click(screen.getByRole('button', { name: /Bring your experience in/ }));
    await user.click(screen.getByRole('button', { name: 'Set permissions' }));
    await user.click(screen.getByRole('checkbox', { name: /Use the sample resume/ }));
    expect(screen.getByRole('button', { name: 'Make it personal' })).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('keeps per-person edits and invalidates review and approval after a draft change', async () => {
    const user = await reviewedDemo();
    expect(screen.getByRole('button', { name: 'Simulate sending' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Personalize' }));
    await user.clear(screen.getByLabelText('Sample email body'));
    await user.type(screen.getByLabelText('Sample email body'), 'My own introduction.');
    await user.click(screen.getByRole('button', { name: 'Jordan' }));
    expect(screen.getByLabelText('Sample email body')).not.toHaveValue('My own introduction.');
    await user.click(screen.getByRole('button', { name: 'Casey' }));
    expect(screen.getByLabelText('Sample email body')).toHaveValue('My own introduction.');
    await user.click(screen.getByRole('button', { name: 'Review messages' }));
    expect(screen.getByLabelText('I approve these sample messages for a simulated send.')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Simulate sending' })).toBeDisabled();
  });

  it('pauses, resumes, finishes, and replays local delivery events without network calls', async () => {
    const user = await reviewedDemo();
    await user.click(screen.getByRole('button', { name: 'Simulate sending' }));
    expect(screen.getByText('Sending')).toBeInTheDocument();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: 'Pause simulation' }));
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.queryAllByText('Delivered')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Resume simulation' }));
    for (let i = 0; i < 5; i += 1) await act(async () => { vi.advanceTimersByTime(1000); });
    expect(screen.getAllByText('Delivered')).toHaveLength(3);
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Restart demo' }));
    expect(screen.queryByText('Delivered')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Your starting point' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Track' })).toBeDisabled();
  }, 15000);

  it('uses immediate simulated results under reduced motion', async () => {
    reduced = true;
    const user = await reviewedDemo();
    await user.click(screen.getByRole('button', { name: 'Simulate sending' }));
    expect(screen.getAllByText('Delivered')).toHaveLength(3);
    expect(screen.queryByRole('button', { name: 'Pause simulation' })).not.toBeInTheDocument();
  });

  it('previews an application, clears input, and never stores or transmits it', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem');
    const user = userEvent.setup();
    render(<LaunchPage />);
    await user.click(screen.getByRole('button', { name: 'Get early access' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveTextContent('Applications are not being collected yet.');
    await user.type(within(dialog).getByLabelText('Your email'), 'fictional@example.com');
    await user.click(within(dialog).getByRole('checkbox'));
    await user.dblClick(within(dialog).getByRole('button', { name: 'Preview my application' }));
    expect(within(dialog).getByRole('status')).toHaveTextContent('No signup, no email, no storage.');
    expect(within(dialog).queryByLabelText('Your email')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    expect(storage).not.toHaveBeenCalled();
    storage.mockRestore();
  });

  it('offers a recoverable form error and clears fields on close', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<WaitlistDialog open onClose={onClose} gateway={{ mode: 'preview', apply: vi.fn().mockRejectedValue(new Error('synthetic')) }} />);
    await user.type(screen.getByLabelText('Your email'), 'fictional@example.com');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Preview my application' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preview my application' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Close application' }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(screen.getByLabelText('Your email')).toHaveValue('');
  });

  it('lets visitors explore each capability without inventing a backend response', async () => {
    const user = userEvent.setup();
    render(<LaunchPage />);
    await user.click(screen.getByRole('button', { name: /Assisted by AI/ }));
    expect(screen.getByText('Human-controlled personalization')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Look beyond the apply button/ }));
    expect(screen.getByText('Job-to-team discovery')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('rejects invalid applications at the adapter boundary', async () => {
    await expect(previewWaitlist.apply({ email: 'invalid', goal: '', consent: true })).rejects.toThrow();
    await expect(previewWaitlist.apply({ email: 'fictional@example.com', goal: '', consent: false })).rejects.toThrow();
    await expect(previewWaitlist.apply({ email: 'fictional@example.com', goal: 'x'.repeat(301), consent: true })).rejects.toThrow();
    await expect(previewWaitlist.apply({ email: 'fictional@example.com', goal: '', consent: true })).resolves.toEqual({ mode: 'preview', stored: false });
  });
});
