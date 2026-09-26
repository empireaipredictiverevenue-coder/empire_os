import { expect } from "chai";
import { network } from "hardhat";

const { ethers, networkHelpers } = await network.create();

const DAY = 24 * 60 * 60;
const DECISION_DELAY = 10 * 60;
const AMOUNT = ethers.parseUnits("125", 18);
const ESCROW_ID = ethers.id("order-001");
const TERMS = ethers.id("commercial-terms-v1");
const EVIDENCE = ethers.id("delivery-evidence-v1");
const DISPUTE = ethers.id("buyer-dispute-v1");

async function deployFixture() {
  const [admin, requester, arbiter, pauser, payer, beneficiary, outsider] =
    await ethers.getSigners();
  const token = await ethers.deployContract("MockUsdt");
  const escrow = await ethers.deployContract("EmpireBscUsdtEscrow", [
    await token.getAddress(), beneficiary.address, admin.address,
    requester.address, arbiter.address, pauser.address, DECISION_DELAY,
  ]);
  await token.mint(payer.address, AMOUNT * 10n);
  return { admin, requester, arbiter, pauser, payer, beneficiary, outsider, token, escrow };
}
async function createAndFund(ctx, escrowId = ESCROW_ID) {
  const now = await networkHelpers.time.latest();
  const fundingDeadline = now + DAY;
  const refundAfter = now + 7 * DAY;
  await ctx.escrow.connect(ctx.requester).createEscrow(
    escrowId, ctx.payer.address, AMOUNT, TERMS, fundingDeadline, refundAfter,
  );
  await ctx.token.connect(ctx.payer).approve(await ctx.escrow.getAddress(), AMOUNT);
  await ctx.escrow.connect(ctx.payer).fundEscrow(escrowId);
  return { fundingDeadline, refundAfter };
}

describe("EmpireBscUsdtEscrow", function () {
  it("funds exact USDT and keeps liability fully backed", async function () {
    const ctx = await deployFixture();
    await createAndFund(ctx);
    const [balance, liability] = await ctx.escrow.escrowBacking();
    expect(balance).to.equal(AMOUNT);
    expect(liability).to.equal(AMOUNT);
    const stored = await ctx.escrow.escrows(ESCROW_ID);
    expect(stored.status).to.equal(2);
  });
  it("rejects unauthorized funding and release approval", async function () {
    const ctx = await deployFixture();
    const now = await networkHelpers.time.latest();
    await ctx.escrow.connect(ctx.requester).createEscrow(
      ESCROW_ID, ctx.payer.address, AMOUNT, TERMS, now + DAY, now + 7 * DAY,
    );
    await expect(ctx.escrow.connect(ctx.outsider).fundEscrow(ESCROW_ID))
      .to.be.revertedWithCustomError(ctx.escrow, "UnauthorizedPayer");
    await ctx.token.connect(ctx.payer).approve(await ctx.escrow.getAddress(), AMOUNT);
    await ctx.escrow.connect(ctx.payer).fundEscrow(ESCROW_ID);
    await expect(ctx.escrow.connect(ctx.outsider).approveRelease(ESCROW_ID, EVIDENCE))
      .to.revert(ethers);
  });

  it("requires delayed governed release and then transfers to beneficiary", async function () {
    const ctx = await deployFixture();
    await createAndFund(ctx);
    await ctx.escrow.connect(ctx.arbiter).approveRelease(ESCROW_ID, EVIDENCE);
    await expect(ctx.escrow.executeResolution(ESCROW_ID))
      .to.be.revertedWithCustomError(ctx.escrow, "TooEarly");
    await networkHelpers.time.increase(DECISION_DELAY);
    await expect(ctx.escrow.executeResolution(ESCROW_ID))
      .to.emit(ctx.escrow, "EscrowReleased");
    expect(await ctx.token.balanceOf(ctx.beneficiary.address)).to.equal(AMOUNT);
  });
  it("lets a dispute cancel a pending release and permits governed refund", async function () {
    const ctx = await deployFixture();
    await createAndFund(ctx);
    await ctx.escrow.connect(ctx.arbiter).approveRelease(ESCROW_ID, EVIDENCE);
    await expect(ctx.escrow.connect(ctx.payer).openDispute(ESCROW_ID, DISPUTE))
      .to.emit(ctx.escrow, "EscrowDisputed");
    const disputed = await ctx.escrow.escrows(ESCROW_ID);
    expect(disputed.status).to.equal(3);
    expect(disputed.resolution).to.equal(0);
    await ctx.escrow.connect(ctx.arbiter).approveRefund(ESCROW_ID, EVIDENCE);
    await networkHelpers.time.increase(DECISION_DELAY);
    await expect(ctx.escrow.executeResolution(ESCROW_ID))
      .to.emit(ctx.escrow, "EscrowRefunded");
    expect(await ctx.token.balanceOf(ctx.payer.address)).to.equal(AMOUNT * 10n);
  });

  it("allows payer timeout refund without arbiter after refundAfter", async function () {
    const ctx = await deployFixture();
    const { refundAfter } = await createAndFund(ctx);
    await networkHelpers.time.increaseTo(refundAfter);
    await expect(ctx.escrow.connect(ctx.payer).claimTimeoutRefund(ESCROW_ID))
      .to.emit(ctx.escrow, "EscrowRefunded");
    expect((await ctx.escrow.escrowBacking())[1]).to.equal(0);
  });
  it("pause blocks release but does not trap approved refunds", async function () {
    const ctx = await deployFixture();
    await createAndFund(ctx);
    await ctx.escrow.connect(ctx.arbiter).approveRelease(ESCROW_ID, EVIDENCE);
    await ctx.escrow.connect(ctx.pauser).pause();
    await networkHelpers.time.increase(DECISION_DELAY);
    await expect(ctx.escrow.executeResolution(ESCROW_ID))
      .to.be.revertedWithCustomError(ctx.escrow, "ReleasePaused");

    await ctx.escrow.connect(ctx.arbiter).cancelResolution(ESCROW_ID);
    await ctx.escrow.connect(ctx.arbiter).approveRefund(ESCROW_ID, EVIDENCE);
    await networkHelpers.time.increase(DECISION_DELAY);
    await expect(ctx.escrow.executeResolution(ESCROW_ID))
      .to.emit(ctx.escrow, "EscrowRefunded");
  });

  it("cannot rescue escrow USDT through the admin rescue path", async function () {
    const ctx = await deployFixture();
    await createAndFund(ctx);
    await expect(
      ctx.escrow.connect(ctx.admin).rescueNonEscrowToken(
        await ctx.token.getAddress(), ctx.admin.address, AMOUNT,
      ),
    ).to.be.revertedWithCustomError(ctx.escrow, "CannotRescueEscrowToken");
  });
});

// Edge-condition regression coverage.
describe("EmpireBscUsdtEscrow edge conditions", function () {
  it("rejects duplicate escrow IDs", async function () {
    const ctx = await deployFixture();
    const now = await networkHelpers.time.latest();
    await ctx.escrow.connect(ctx.requester).createEscrow(
      ESCROW_ID, ctx.payer.address, AMOUNT, TERMS, now + DAY, now + 7 * DAY,
    );
    await expect(ctx.escrow.connect(ctx.requester).createEscrow(
      ESCROW_ID, ctx.payer.address, AMOUNT, TERMS, now + DAY, now + 7 * DAY,
    )).to.be.revertedWithCustomError(ctx.escrow, "EscrowExists");
  });

  it("rejects funding after the approved funding deadline", async function () {
    const ctx = await deployFixture();
    const now = await networkHelpers.time.latest();
    await ctx.escrow.connect(ctx.requester).createEscrow(
      ESCROW_ID, ctx.payer.address, AMOUNT, TERMS, now + 60, now + DAY,
    );
    await ctx.token.connect(ctx.payer).approve(await ctx.escrow.getAddress(), AMOUNT);
    await networkHelpers.time.increase(61);
    await expect(ctx.escrow.connect(ctx.payer).fundEscrow(ESCROW_ID))
      .to.be.revertedWithCustomError(ctx.escrow, "FundingExpired");
  });
  it("rejects zero terms hash and invalid windows", async function () {
    const ctx = await deployFixture();
    const now = await networkHelpers.time.latest();
    await expect(ctx.escrow.connect(ctx.requester).createEscrow(
      ESCROW_ID, ctx.payer.address, AMOUNT, ethers.ZeroHash, now + DAY, now + 7 * DAY,
    )).to.be.revertedWithCustomError(ctx.escrow, "InvalidTermsHash");
    await expect(ctx.escrow.connect(ctx.requester).createEscrow(
      ethers.id("bad-window"), ctx.payer.address, AMOUNT, TERMS,
      now + 8 * DAY, now + 9 * DAY,
    )).to.be.revertedWithCustomError(ctx.escrow, "InvalidWindow");
  });

  it("payer can cancel an unfunded escrow but cannot cancel after funding", async function () {
    const ctx = await deployFixture();
    const now = await networkHelpers.time.latest();
    await ctx.escrow.connect(ctx.requester).createEscrow(
      ESCROW_ID, ctx.payer.address, AMOUNT, TERMS, now + DAY, now + 7 * DAY,
    );
    await expect(ctx.escrow.connect(ctx.payer).cancelUnfunded(ESCROW_ID))
      .to.emit(ctx.escrow, "EscrowCancelled");
    const otherId = ethers.id("order-002");
    await createAndFund(ctx, otherId);
    await expect(ctx.escrow.connect(ctx.payer).cancelUnfunded(otherId))
      .to.be.revertedWithCustomError(ctx.escrow, "InvalidState");
  });
});


describe("EmpireBscUsdtEscrow timeout precedence", function () {
  it("payer timeout refund wins even if a release is pending", async function () {
    const ctx = await deployFixture();
    const { refundAfter } = await createAndFund(ctx);
    await ctx.escrow.connect(ctx.arbiter).approveRelease(ESCROW_ID, EVIDENCE);
    await networkHelpers.time.increaseTo(refundAfter);
    await expect(ctx.escrow.connect(ctx.payer).claimTimeoutRefund(ESCROW_ID))
      .to.emit(ctx.escrow, "EscrowRefunded");
    const stored = await ctx.escrow.escrows(ESCROW_ID);
    expect(stored.status).to.equal(6);
    expect(stored.resolution).to.equal(0);
    expect(await ctx.token.balanceOf(ctx.payer.address)).to.equal(AMOUNT * 10n);
  });

  it("payer timeout refund also works from disputed state", async function () {
    const ctx = await deployFixture();
    const { refundAfter } = await createAndFund(ctx);
    await ctx.escrow.connect(ctx.payer).openDispute(ESCROW_ID, DISPUTE);
    await networkHelpers.time.increaseTo(refundAfter);
    await ctx.escrow.connect(ctx.payer).claimTimeoutRefund(ESCROW_ID);
    expect((await ctx.escrow.escrows(ESCROW_ID)).status).to.equal(6);
  });
});
