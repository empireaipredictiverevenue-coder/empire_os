// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract EmpireBscUsdtEscrow is AccessControlDefaultAdminRules, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    address public constant BSC_USDT = 0x55d398326f99059fF775485246999027B3197955;
    bytes32 public constant REQUESTER_ROLE = keccak256("REQUESTER_ROLE");
    bytes32 public constant ARBITER_ROLE = keccak256("ARBITER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint48 public constant MIN_DECISION_DELAY = 10 minutes;
    uint48 public constant MAX_DECISION_DELAY = 7 days;
    uint48 public constant MAX_FUNDING_WINDOW = 7 days;
    uint48 public constant MAX_ESCROW_LIFETIME = 365 days;

    enum Status {
        None,
        Open,
        Funded,
        Disputed,
        ResolutionPending,
        Released,
        Refunded,
        Cancelled
    }

    enum Resolution {
        None,
        Release,
        Refund
    }

    struct Escrow {
        address payer;
        uint256 amount;
        bytes32 termsHash;
        uint48 createdAt;
        uint48 fundingDeadline;
        uint48 refundAfter;
        uint48 executableAt;
        Status status;
        Resolution resolution;
        bytes32 decisionEvidenceHash;
    }

    IERC20 public immutable token;
    address public immutable beneficiary;
    uint48 public immutable decisionDelay;
    uint256 public totalEscrowed;

    mapping(bytes32 escrowId => Escrow) public escrows;

    error InvalidAddress();
    error InvalidAmount();
    error InvalidTermsHash();
    error InvalidWindow();
    error InvalidState(Status current);
    error UnauthorizedPayer();
    error WrongToken();
    error WrongTokenDecimals(uint8 decimals);
    error ExactFundingRequired(uint256 expected, uint256 received);
    error TooEarly(uint48 availableAt);
    error ResolutionMissing();
    error EscrowExists();
    error EscrowMissing();
    error DecisionEvidenceRequired();
    error CannotRescueEscrowToken();
    error FundingExpired(uint48 deadline);
    error ReleasePaused();

    event EscrowCreated(
        bytes32 indexed escrowId,
        address indexed payer,
        uint256 amount,
        bytes32 indexed termsHash,
        uint48 fundingDeadline,
        uint48 refundAfter
    );
    event EscrowFunded(bytes32 indexed escrowId, address indexed payer, uint256 amount);

    event EscrowDisputed(bytes32 indexed escrowId, address indexed raisedBy, bytes32 reasonHash);
    event ResolutionApproved(
        bytes32 indexed escrowId,
        Resolution resolution,
        bytes32 indexed evidenceHash,
        uint48 executableAt
    );
    event ResolutionCancelled(bytes32 indexed escrowId, address indexed actor);
    event EscrowReleased(bytes32 indexed escrowId, address indexed beneficiary, uint256 amount);
    event EscrowRefunded(bytes32 indexed escrowId, address indexed payer, uint256 amount);
    event EscrowCancelled(bytes32 indexed escrowId, address indexed actor);

    constructor(
        IERC20Metadata token_,
        address beneficiary_,
        address initialAdmin,
        address requester,
        address arbiter,
        address pauser,
        uint48 decisionDelay_
    ) AccessControlDefaultAdminRules(2 days, initialAdmin) {
        if (
            address(token_) == address(0) || beneficiary_ == address(0)
                || initialAdmin == address(0) || requester == address(0)
                || arbiter == address(0) || pauser == address(0)
        ) revert InvalidAddress();
        if (requester == arbiter) revert InvalidAddress();
        if (block.chainid == 56 && address(token_) != BSC_USDT) revert WrongToken();
        uint8 decimals = token_.decimals();
        if (decimals != 18) revert WrongTokenDecimals(decimals);
        if (decisionDelay_ < MIN_DECISION_DELAY || decisionDelay_ > MAX_DECISION_DELAY) {
            revert InvalidWindow();
        }
        token = IERC20(address(token_));
        beneficiary = beneficiary_;
        decisionDelay = decisionDelay_;
        _grantRole(REQUESTER_ROLE, requester);
        _grantRole(ARBITER_ROLE, arbiter);
        _grantRole(PAUSER_ROLE, pauser);
    }

    function createEscrow(
        bytes32 escrowId,
        address payer,
        uint256 amount,
        bytes32 termsHash,
        uint48 fundingDeadline,
        uint48 refundAfter
    ) external onlyRole(REQUESTER_ROLE) whenNotPaused {
        if (escrowId == bytes32(0)) revert EscrowMissing();
        if (escrows[escrowId].status != Status.None) revert EscrowExists();
        if (payer == address(0) || payer == beneficiary || payer == address(this)) {
            revert InvalidAddress();
        }
        if (amount == 0) revert InvalidAmount();
        if (termsHash == bytes32(0)) revert InvalidTermsHash();
        uint48 nowTs = uint48(block.timestamp);
        if (
            fundingDeadline <= nowTs
                || fundingDeadline > nowTs + MAX_FUNDING_WINDOW
                || refundAfter <= fundingDeadline
                || refundAfter > nowTs + MAX_ESCROW_LIFETIME
        ) revert InvalidWindow();

        escrows[escrowId] = Escrow({
            payer: payer,
            amount: amount,
            termsHash: termsHash,
            createdAt: nowTs,
            fundingDeadline: fundingDeadline,
            refundAfter: refundAfter,
            executableAt: 0,
            status: Status.Open,
            resolution: Resolution.None,
            decisionEvidenceHash: bytes32(0)
        });
        emit EscrowCreated(escrowId, payer, amount, termsHash, fundingDeadline, refundAfter);
    }

    function fundEscrow(bytes32 escrowId) external nonReentrant whenNotPaused {
        Escrow storage e = _escrow(escrowId);
        if (e.status != Status.Open) revert InvalidState(e.status);
        if (msg.sender != e.payer) revert UnauthorizedPayer();
        if (block.timestamp > e.fundingDeadline) revert FundingExpired(e.fundingDeadline);

        uint256 beforeBalance = token.balanceOf(address(this));
        token.safeTransferFrom(msg.sender, address(this), e.amount);
        uint256 received = token.balanceOf(address(this)) - beforeBalance;
        if (received != e.amount) revert ExactFundingRequired(e.amount, received);

        e.status = Status.Funded;
        totalEscrowed += e.amount;
        emit EscrowFunded(escrowId, msg.sender, e.amount);
    }

    function cancelUnfunded(bytes32 escrowId) external {
        Escrow storage e = _escrow(escrowId);
        if (e.status != Status.Open) revert InvalidState(e.status);
        if (msg.sender != e.payer && !hasRole(REQUESTER_ROLE, msg.sender)) {
            revert UnauthorizedPayer();
        }
        e.status = Status.Cancelled;
        emit EscrowCancelled(escrowId, msg.sender);
    }

    function openDispute(bytes32 escrowId, bytes32 reasonHash) external {
        Escrow storage e = _escrow(escrowId);
        if (msg.sender != e.payer && !hasRole(ARBITER_ROLE, msg.sender)) {
            revert UnauthorizedPayer();
        }
        if (reasonHash == bytes32(0)) revert DecisionEvidenceRequired();
        if (e.status != Status.Funded && e.status != Status.ResolutionPending) {
            revert InvalidState(e.status);
        }
        e.status = Status.Disputed;
        e.resolution = Resolution.None;
        e.executableAt = 0;
        e.decisionEvidenceHash = bytes32(0);
        emit EscrowDisputed(escrowId, msg.sender, reasonHash);
    }

    function approveRelease(bytes32 escrowId, bytes32 evidenceHash)
        external onlyRole(ARBITER_ROLE) whenNotPaused
    {
        _approveResolution(escrowId, Resolution.Release, evidenceHash);
    }

    function approveRefund(bytes32 escrowId, bytes32 evidenceHash)
        external onlyRole(ARBITER_ROLE)
    {
        _approveResolution(escrowId, Resolution.Refund, evidenceHash);
    }

    function _approveResolution(
        bytes32 escrowId,
        Resolution resolution,
        bytes32 evidenceHash
    ) private {
        Escrow storage e = _escrow(escrowId);
        if (e.status != Status.Funded && e.status != Status.Disputed) {
            revert InvalidState(e.status);
        }
        if (evidenceHash == bytes32(0)) revert DecisionEvidenceRequired();
        e.status = Status.ResolutionPending;
        e.resolution = resolution;
        e.decisionEvidenceHash = evidenceHash;
        e.executableAt = uint48(block.timestamp) + decisionDelay;
        emit ResolutionApproved(escrowId, resolution, evidenceHash, e.executableAt);
    }

    function cancelResolution(bytes32 escrowId)
        external onlyRole(ARBITER_ROLE)
    {
        Escrow storage e = _escrow(escrowId);
        if (e.status != Status.ResolutionPending) revert InvalidState(e.status);
        e.status = Status.Disputed;
        e.resolution = Resolution.None;
        e.executableAt = 0;
        e.decisionEvidenceHash = bytes32(0);
        emit ResolutionCancelled(escrowId, msg.sender);
    }

    function executeResolution(bytes32 escrowId)
        external nonReentrant
    {
        Escrow storage e = _escrow(escrowId);
        if (e.status != Status.ResolutionPending) revert InvalidState(e.status);
        if (block.timestamp < e.executableAt) revert TooEarly(e.executableAt);
        Resolution resolution = e.resolution;
        if (paused() && resolution == Resolution.Release) revert ReleasePaused();
        if (resolution == Resolution.None) revert ResolutionMissing();

        uint256 amount = e.amount;
        totalEscrowed -= amount;
        if (resolution == Resolution.Release) {
            e.status = Status.Released;
            token.safeTransfer(beneficiary, amount);
            emit EscrowReleased(escrowId, beneficiary, amount);
        } else {
            e.status = Status.Refunded;
            token.safeTransfer(e.payer, amount);
            emit EscrowRefunded(escrowId, e.payer, amount);
        }
    }

    function claimTimeoutRefund(bytes32 escrowId)
        external nonReentrant
    {
        Escrow storage e = _escrow(escrowId);
        if (msg.sender != e.payer) revert UnauthorizedPayer();
        if (
            e.status != Status.Funded
                && e.status != Status.Disputed
                && e.status != Status.ResolutionPending
        ) revert InvalidState(e.status);
        if (block.timestamp < e.refundAfter) revert TooEarly(e.refundAfter);

        e.status = Status.Refunded;
        e.resolution = Resolution.None;
        e.executableAt = 0;
        e.decisionEvidenceHash = bytes32(0);
        totalEscrowed -= e.amount;
        token.safeTransfer(e.payer, e.amount);
        emit EscrowRefunded(escrowId, e.payer, e.amount);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function rescueNonEscrowToken(IERC20 otherToken, address to, uint256 amount)
        external onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (address(otherToken) == address(token)) revert CannotRescueEscrowToken();
        if (to == address(0)) revert InvalidAddress();
        otherToken.safeTransfer(to, amount);
    }

    function escrowBacking() external view returns (uint256 balance, uint256 liability) {
        balance = token.balanceOf(address(this));
        liability = totalEscrowed;
    }

    function _escrow(bytes32 escrowId) private view returns (Escrow storage e) {
        e = escrows[escrowId];
        if (e.status == Status.None) revert EscrowMissing();
    }
}
